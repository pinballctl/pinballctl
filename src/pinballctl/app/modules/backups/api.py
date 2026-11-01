"""Durable operation status with no hardware or restore work in upload handlers."""
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
from threading import Thread
import uuid

from flask import current_app, jsonify, request, send_file
from itsdangerous import URLSafeTimedSerializer, BadSignature

from pinballctl.backup import service
from pinballctl.backup.ownership import COMPONENTS
from . import api_bp


def signer():
    return URLSafeTimedSerializer(current_app.secret_key,salt='backup-restore-v1')


def job_path(ident):
    service.check(isinstance(ident,str) and service.ID.fullmatch(ident),'Invalid job ID')
    return service.library_root(current_app.instance_path)/'jobs'/(ident+'.json')


def start_job(operation):
    app=current_app._get_current_object();ident=uuid.uuid4().hex
    path=job_path(ident)
    status={'id':ident,'state':'running','message':'Preparing…','pid':os.getpid(),'createdAt':datetime.now(timezone.utc).isoformat()}
    service.write_json(path,status)
    lease=path.with_suffix('.lock').open('a')
    fcntl.flock(lease,fcntl.LOCK_EX)
    def run():
        try:
            with app.app_context():
                def progress(**values):status.update(values);service.write_json(path,status)
                try:
                    result=operation(progress)
                    status.update(state='done',message='Complete',result=result)
                except Exception as exc:
                    app.logger.exception('Backup / Restore operation failed')
                    status.update(state='error',message=str(exc))
                try:service.write_json(path,status)
                except OSError:app.logger.exception('Could not persist backup operation outcome')
        finally:
            lease.close()
    Thread(target=run,daemon=True,name='backup-'+ident[:8]).start()
    return jsonify(ok=True,jobId=ident),202


@api_bp.get('/list')
def listing():
    rows,errors=service.list_backups(current_app.instance_path)
    summaries=[{**{k:v for k,v in row.items() if k!='inventory'},'fileCount':len(row['inventory'])} for row in rows]
    return jsonify(ok=True,backups=summaries,components=COMPONENTS,diagnostics=errors,
                   policy='Credentials, session keys, browser profiles, active state, logs and caches are excluded. Restore automatically stops and restarts a previously running bridge; stop playback first.')


@api_bp.get('/view/<ident>')
def view(ident):
    try:
        path=service.archive_path(current_app.instance_path,ident)
        with service.validated_archive(path,verify=False) as (_,manifest):
            return jsonify(ok=True,backup={'id':ident,**manifest,'archiveSize':path.stat().st_size})
    except (ValueError,OSError) as exc:return jsonify(ok=False,error=str(exc)),400


@api_bp.get('/download/<ident>')
def download(ident):
    try:
        path=service.archive_path(current_app.instance_path,ident)
        return send_file(path,as_attachment=True,download_name='pinballctl-backup-'+ident+'.zip',max_age=0)
    except (ValueError,OSError) as exc:return jsonify(ok=False,error=str(exc)),400


@api_bp.post('/delete/<ident>')
def delete(ident):
    try:
        service.check((request.get_json(silent=True) or {}).get('confirmation')=='DELETE','Confirm deletion')
        store=service.library_root(current_app.instance_path)
        service.check(not any(service.read_json(p).get('state')=='applying' and service.read_json(p).get('recoveryId')==ident for p in (store/'transactions').glob('*/journal.json')), 'Recovery backup is in use by an active restore')
        service.archive_path(current_app.instance_path,ident).unlink()
        return jsonify(ok=True)
    except (ValueError,OSError) as exc:return jsonify(ok=False,error=str(exc)),400


@api_bp.post('/create')
def create():
    try:
        body=request.get_json(silent=True) or {}
        components=service.selected_components(body.get('components'));comment=body.get('comment','')
        service.check(isinstance(comment,str) and len(comment)<=2000,'Comment too long')
        instance=current_app.instance_path
        return start_job(lambda progress:service.create(instance,components,comment,progress))
    except (ValueError,TypeError) as exc:return jsonify(ok=False,error=str(exc)),400


@api_bp.post('/upload')
def upload():
    try:
        request.max_content_length=service.MAX_TOTAL+1024**2
        file=request.files.get('file')
        service.check(file is not None,'Choose a ZIP file')
        instance=current_app.instance_path;folder=service.library_root(instance)/'uploads';folder.mkdir(exist_ok=True,mode=0o700)
        staged=folder/(uuid.uuid4().hex+'.zip');size=0
        try:
            with staged.open('xb') as output:
                os.chmod(staged,0o600)
                while chunk:=file.stream.read(1024**2):
                    size+=len(chunk);service.check(size<=service.MAX_TOTAL,'Upload exceeds 8 GiB');output.write(chunk)
        except Exception:
            staged.unlink(missing_ok=True);raise
        def operation(progress):
            try:
                progress(message='Validating ZIP inventory and checksums…')
                with staged.open('rb') as source:return service.upload(instance,source)
            finally:staged.unlink(missing_ok=True)
        return start_job(operation)
    except (ValueError,OSError) as exc:return jsonify(ok=False,error=str(exc)),400


@api_bp.post('/preview')
def preview():
    body=request.get_json(silent=True) or {};sequence=body.get('sequence');clear=body.get('removeOtherContent',False)
    app=current_app._get_current_object();instance=app.instance_path
    def operation(progress):
        progress(message='Validating archives and final dependencies…')
        report=service.preview(instance,sequence,clear)
        token=URLSafeTimedSerializer(app.secret_key,salt='backup-restore-v1').dumps({'sequence':sequence,'clear':clear,'report':report})
        return {'preview':report,'token':token}
    return start_job(operation)


@api_bp.post('/restore')
def restore():
    try:
        body=request.get_json(silent=True) or {}
        payload=signer().loads(body.get('token',''),max_age=1800)
        required='REMOVE OTHER CONTENT' if payload['clear'] else 'REPLACE'
        service.check(body.get('confirmation')==required,'Type '+required+' to confirm')
        instance=current_app.instance_path
        from pinballctl.backup.lifecycle import restore as managed_restore
        return start_job(lambda progress:managed_restore(instance,payload['sequence'],payload['clear'],payload['report'],progress))
    except (ValueError,TypeError,KeyError,BadSignature) as exc:return jsonify(ok=False,error=str(exc)),400


@api_bp.get('/jobs/<ident>')
def job(ident):
    try:
        status=service.read_json(job_path(ident))
        service.check(bool(status),'Job not found')
        if status['state']=='running':
            # A job lease survives cross-worker polling and releases if its thread
            # exits or its process is killed, even when writing status fails.
            lock=job_path(ident).with_suffix('.lock')
            interrupted=not lock.exists()
            if lock.exists():
                with lock.open('a') as probe:
                    try:fcntl.flock(probe,fcntl.LOCK_EX|fcntl.LOCK_NB);interrupted=True
                    except BlockingIOError:pass
            if interrupted:
                status.update(state='error',message='Operation interrupted. Reload web service to run pending restore recovery.')
                try:service.write_json(job_path(ident),status)
                except OSError:pass
        return jsonify(ok=True,job=status)
    except (ValueError,OSError) as exc:return jsonify(ok=False,error=str(exc)),400


@api_bp.post('/pause-bridge')
def pause_bridge():
    try:
        service.check((request.get_json(silent=True) or {}).get('confirmation')=='PAUSE BRIDGE','Confirm maintenance interruption')
        def operation(progress):
            progress(message='Stopping bridge for maintenance. It will remain stopped.')
            from pinballctl.cli import _stop_bridge_process, _default_bridge_pidfile, _bridge_running_via_lock
            stopped=_stop_bridge_process(_default_bridge_pidfile())
            running,_=_bridge_running_via_lock()
            service.check(not running,'Bridge did not stop; restore remains blocked')
            from pinballctl.bridge.state import write_state
            write_state(connected=False,connection_reason='backup_maintenance')
            return {'stopped':stopped,'message':'Bridge remains stopped. Restore does not restart or arm it.'}
        return start_job(operation)
    except ValueError as exc:return jsonify(ok=False,error=str(exc)),400
