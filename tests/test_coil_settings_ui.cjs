const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const base = path.join(__dirname, '../src/pinballctl/app/modules/hardware');
function load() {
  const fields = {innerHTML:'', nodes:[], querySelector(){return null;}, querySelectorAll(){return this.nodes;}};
  const context = {textContent:'', innerHTML:''};
  const root = {querySelector(){return null;}};
  const document = {
    getElementById(id) { return {'hardware-root':root,'hardware-driver-config-fields':fields,'hardware-driver-config-context':context}[id] || null; },
    createElement(){return {};}
  };
  const sandbox = {document, window:{}, console};
  let source = fs.readFileSync(path.join(base,'static/js/hardware.js'),'utf8');
  source = source.replace('  init();', `globalThis.api = {
    setup(profiles, rows) {functionProfiles=profiles; mapping=rows; pins=Object.keys(rows).map(uid=>({uid,chan:uid}));},
    open(uid) {activeDriverConfigUid=uid; renderDriverConfigModal(uid);},
    flush:flushDriverConfigFormToMapping, get(uid){return mapping[uid];}, config:driverConfigForRow,
    normalize:normalizeFieldValue
  };`);
  vm.runInNewContext(source,sandbox);
  return {api:sandbox.api, fields, context};
}
const profiles = JSON.parse(fs.readFileSync(path.join(base,'drivers.json'),'utf8')).functions;
test('existing coils get individual options without linked-pin or duplicate polarity fields', () => {
  const {api,fields} = load();
  api.setup(profiles, {six:{function:'Coil',driver:'Default',safety:'LOW'},seven:{function:'Coil',driver:'Default',safety:'HIGH'}});
  assert.ok(api.config(api.get('six')));
  api.open('six');
  assert.match(fields.innerHTML,/coilMaxOnMs/);
  assert.match(fields.innerHTML,/value="20"/);
  assert.match(fields.innerHTML,/value="1000"/);
  assert.doesNotMatch(fields.innerHTML,/hardware-driver-link-|coilOffLevel/);
  fields.nodes = ['coilMaxOnMs','coilMinOffMs','coilEnabled'].map((key,i)=>({getAttribute(){return key;},value:['60','2000','Enabled'][i]}));
  api.flush();
  assert.equal(api.get('six').coilMaxOnMs,60);
  assert.equal(api.get('seven').coilMaxOnMs,undefined);
  assert.equal(api.get('seven').safety,'HIGH');
});
test('linked display configuration still includes pin roles', () => {
  const {api,fields} = load();
  const name = Object.keys(profiles).find(name=>profiles[name].drivers.some(d=>d.link?.enabled));
  const driver = profiles[name].drivers.find(d=>d.link?.enabled);
  api.setup(profiles,{one:{function:name,driver:driver.name}});
  api.open('one');
  assert.match(fields.innerHTML,/hardware-driver-link-role/);
  assert.match(fields.innerHTML,/hardware-driver-link-secondary/);
});
test('safety overrides are not silently clamped or rounded', () => {
  const {api} = load();
  const field = profiles.Coil.drivers[0].settings.find(f=>f.key==='coilMaxOnMs');
  assert.equal(api.normalize(field,'2000'),2000);
  assert.equal(api.normalize(field,'1.5'),1.5);
  assert.equal(api.normalize(field,''),'');
});
test('mode selection exposes only applicable controls and filters linked hold pins', () => {
  const {api,fields} = load();
  const power='ESP__MAIN__GPIO__6', hold='ESP__MAIN__GPIO__7', other='OTHER__MAIN__GPIO__7';
  api.setup(profiles, {
    [power]:{function:'Coil',driver:'Default',coilMode:'Pulse + PWM hold'},
    [hold]:{function:'Coil',driver:'Default',coilMode:'Hold winding'},
    [other]:{function:'Coil',driver:'Default',coilMode:'Hold winding'}
  });
  api.open(power);
  assert.match(fields.innerHTML,/data-setting-key="coilHoldDuty"/);
  assert.match(fields.innerHTML,/data-setting-key="coilPwmHz"/);
  assert.doesNotMatch(fields.innerHTML,/data-setting-key="coilHoldPinUid"/);
  api.get(power).coilMode='Separate power and hold'; api.open(power);
  assert.match(fields.innerHTML,new RegExp(`value="${hold}"`));
  assert.doesNotMatch(fields.innerHTML,new RegExp(`value="${other}"`));
  assert.doesNotMatch(fields.innerHTML,/data-setting-key="coilHoldDuty"/);
  api.get(power).coilMode='Continuous duty'; api.open(power);
  assert.match(fields.innerHTML,/data-setting-key="coilMaxHoldMs"/);
  assert.doesNotMatch(fields.innerHTML,/data-setting-key="coilPulseMs"/);
});
