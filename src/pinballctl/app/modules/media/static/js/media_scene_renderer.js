(() => {
  function clamp(v, lo, hi) {
    const n = Number(v);
    if (!Number.isFinite(n)) return lo;
    return Math.max(lo, Math.min(hi, n));
  }

  function esc(text) {
    return String(text ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function normalizeTextEffects(raw) {
    const allowed = new Set(["shadow", "outline", "underline", "strike", "bold", "italic", "uppercase", "tracking", "glow"]);
    const out = [];
    const list = Array.isArray(raw) ? raw : [];
    list.forEach((item) => {
      const key = String(item || "").trim().toLowerCase();
      if (!allowed.has(key)) return;
      if (out.includes(key)) return;
      out.push(key);
    });
    return out;
  }

  function normalizeTextAlign(raw) {
    const t = String(raw || "").trim().toLowerCase();
    return ["left", "center", "right"].includes(t) ? t : "center";
  }

  function parseColorRgb(rawColor) {
    const s = String(rawColor || "").trim().toLowerCase();
    if (!s) return null;
    if (s.startsWith("#")) {
      const hex = s.slice(1);
      if (hex.length === 3 || hex.length === 4) {
        const r = parseInt(hex[0] + hex[0], 16);
        const g = parseInt(hex[1] + hex[1], 16);
        const b = parseInt(hex[2] + hex[2], 16);
        if ([r, g, b].every((n) => Number.isFinite(n))) return { r, g, b };
      } else if (hex.length === 6 || hex.length === 8) {
        const r = parseInt(hex.slice(0, 2), 16);
        const g = parseInt(hex.slice(2, 4), 16);
        const b = parseInt(hex.slice(4, 6), 16);
        if ([r, g, b].every((n) => Number.isFinite(n))) return { r, g, b };
      }
      return null;
    }
    const m = s.match(/^rgba?\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)(?:\s*,\s*[0-9.]+\s*)?\)$/);
    if (!m) return null;
    const r = clamp(Number(m[1]), 0, 255);
    const g = clamp(Number(m[2]), 0, 255);
    const b = clamp(Number(m[3]), 0, 255);
    return { r: Math.round(r), g: Math.round(g), b: Math.round(b) };
  }

  function srgbToLinear(v) {
    const n = clamp(Number(v) / 255, 0, 1);
    if (n <= 0.04045) return n / 12.92;
    return ((n + 0.055) / 1.055) ** 2.4;
  }

  function relativeLuminance(rgb) {
    if (!rgb) return null;
    const r = srgbToLinear(rgb.r);
    const g = srgbToLinear(rgb.g);
    const b = srgbToLinear(rgb.b);
    return (0.2126 * r) + (0.7152 * g) + (0.0722 * b);
  }

  function effectRgbFromTextColor(rawColor) {
    const rgb = parseColorRgb(rawColor);
    const lum = relativeLuminance(rgb);
    if (!Number.isFinite(lum)) return { r: 0, g: 0, b: 0 };
    return lum >= 0.56 ? { r: 0, g: 0, b: 0 } : { r: 255, g: 255, b: 255 };
  }

  function rgba(rgb, alpha) {
    return `rgba(${rgb.r},${rgb.g},${rgb.b},${alpha})`;
  }

  function textEffectStyles(ovType, rawEffects, textColor) {
    if (String(ovType || "") !== "text") {
      return {
        fontWeight: "400",
        fontStyle: "normal",
        textTransform: "none",
        letterSpacing: "normal",
        textDecoration: "none",
        textShadow: "none",
      };
    }
    const fx = new Set(normalizeTextEffects(rawEffects));
    const fxRgb = effectRgbFromTextColor(textColor);
    const decorations = [];
    if (fx.has("underline")) decorations.push("underline");
    if (fx.has("strike")) decorations.push("line-through");
    const shadows = [];
    if (fx.has("outline")) {
      shadows.push(`-1px 0 0 ${rgba(fxRgb, 0.92)}`);
      shadows.push(`1px 0 0 ${rgba(fxRgb, 0.92)}`);
      shadows.push(`0 -1px 0 ${rgba(fxRgb, 0.92)}`);
      shadows.push(`0 1px 0 ${rgba(fxRgb, 0.92)}`);
    }
    if (fx.has("shadow")) shadows.push(`0 2px 6px ${rgba(fxRgb, 0.78)}`);
    if (fx.has("glow")) shadows.push(`0 0 6px ${rgba(fxRgb, 0.42)}, 0 0 14px ${rgba(fxRgb, 0.24)}`);
    return {
      fontWeight: fx.has("bold") ? "700" : "400",
      fontStyle: fx.has("italic") ? "italic" : "normal",
      textTransform: fx.has("uppercase") ? "uppercase" : "none",
      letterSpacing: fx.has("tracking") ? "0.06em" : "normal",
      textDecoration: decorations.length ? decorations.join(" ") : "none",
      textShadow: shadows.length ? shadows.join(", ") : "none",
    };
  }

  function sanitizeFit(rawFit) {
    const fit = String(rawFit || "contain").toLowerCase();
    return ["cover", "contain", "fill", "none", "scale-down"].includes(fit) ? fit : "contain";
  }

  function normalizeOverlayType(raw) {
    const t = String(raw || "").trim().toLowerCase();
    if (t === "badge") return "text";
    if (t === "frame") return "image";
    return ["text", "image"].includes(t) ? t : "";
  }

  function defaultOverlayText(ov, values) {
    const key = String(ov?.valueKey || "").trim();
    if (key) {
      const value = values && Object.prototype.hasOwnProperty.call(values, key) ? values[key] : "";
      if (value !== undefined && value !== null && String(value) !== "") return String(value);
    }
    return String(ov?.text || "");
  }

  function defaultAssetUrlBuilder(assetId, layer, kind) {
    return assetId ? `/api/media/assets/file/${encodeURIComponent(assetId)}` : "";
  }

  function defaultLayerId(layer, index) {
    return String(layer?.layerId || layer?.scene?.id || `layer_${index + 1}`);
  }

  function defaultOverlayId(ov, layer, overlayIndex, layerIndex) {
    return `${defaultLayerId(layer, layerIndex)}:${String(ov?.id || `ov_${overlayIndex + 1}`)}`;
  }

  function fitTextOverlayNode(node, maxFontPx) {
    if (!(node instanceof HTMLElement)) return;
    const textEl = node.querySelector(".media-preview-overlay-text-content");
    if (!(textEl instanceof HTMLElement)) return;
    const basePx = Math.max(8, Number(maxFontPx || 24));
    const widthCap = Math.max(8, Math.floor((node.clientWidth || 0) * 0.92));
    const heightCap = Math.max(8, Math.floor((node.clientHeight || 0) * 0.92));
    const maxPx = Math.max(basePx, widthCap, heightCap);
    let low = 8;
    let high = Math.max(8, Math.floor(maxPx));
    let best = low;
    textEl.style.fontSize = `${high}px`;
    const fits = () => (textEl.scrollWidth <= node.clientWidth + 1) && (textEl.scrollHeight <= node.clientHeight + 1);
    if (fits()) {
      best = high;
    } else {
      while (low <= high) {
        const mid = Math.floor((low + high) / 2);
        textEl.style.fontSize = `${mid}px`;
        if (fits()) {
          best = mid;
          low = mid + 1;
        } else {
          high = mid - 1;
        }
      }
    }
    textEl.style.fontSize = `${best}px`;
    node.dataset.fittedFontPx = String(best);
  }

  function createSceneRenderer(options) {
    const layersRoot = options?.layersRoot || null;
    const overlayRoot = options?.overlayRoot || null;
    const layerClassName = String(options?.layerClassName || "media-layer");
    const overlayClassName = String(options?.overlayClassName || "media-scene-overlay");
    const overlayImageLayerClassName = String(options?.overlayImageLayerClassName || "");
    const overlayTextLayerClassName = String(options?.overlayTextLayerClassName || "");
    const imageClassName = String(options?.imageClassName || "ov-img");
    const videoIdForLayer = typeof options?.videoIdForLayer === "function" ? options.videoIdForLayer : () => "";
    const mediaClassNameForLayer = typeof options?.mediaClassNameForLayer === "function" ? options.mediaClassNameForLayer : () => "";
    const assetUrlFor = typeof options?.assetUrlFor === "function" ? options.assetUrlFor : defaultAssetUrlBuilder;
    const overlayTextFor = typeof options?.overlayTextFor === "function" ? options.overlayTextFor : defaultOverlayText;
    const layerIdFor = typeof options?.layerIdFor === "function" ? options.layerIdFor : defaultLayerId;
    const overlayIdFor = typeof options?.overlayIdFor === "function" ? options.overlayIdFor : defaultOverlayId;
    const onVideoEnded = typeof options?.onVideoEnded === "function" ? options.onVideoEnded : null;
    const decorateOverlayNode = typeof options?.decorateOverlayNode === "function" ? options.decorateOverlayNode : null;

    function setNodeClasses(node, classNames) {
      node.className = classNames.filter(Boolean).join(" ");
    }

    function syncElementClasses(node, classNames) {
      const wanted = new Set(
        classNames
          .flatMap((value) => String(value || "").split(/\s+/))
          .map((value) => value.trim())
          .filter(Boolean)
      );
      [...node.classList].forEach((name) => {
        if (!wanted.has(name)) node.classList.remove(name);
      });
      wanted.forEach((name) => node.classList.add(name));
    }

    function applyTransitionToNode(node, transition, baseTransform = "") {
      const phase = String(transition?.phase || "").trim().toLowerCase();
      const type = String(transition?.type || "CUT").trim().toUpperCase();
      const durationMs = Math.max(0, Math.round(Number(transition?.durationMs || 0)));
      const anchorMs = Math.max(0, Math.round(Number(transition?.anchorMs || 0)));
      const finalTransform = String(baseTransform || "").trim();
      const zoomTransform = finalTransform ? `${finalTransform} scale(1.18)` : "scale(1.18)";
      const hiddenTransform = type === "ZOOM" ? zoomTransform : finalTransform;
      const sig = `${phase}|${type}|${durationMs}|${anchorMs}|${finalTransform}`;

      if (!phase || durationMs <= 0 || type === "CUT") {
        node.dataset.transitionSig = "";
        node.style.transition = "";
        node.style.willChange = "";
        node.style.opacity = "1";
        node.style.transform = finalTransform;
        return;
      }
      if (node.dataset.transitionSig === sig) return;
      node.dataset.transitionSig = sig;
      node.style.willChange = "opacity, transform";
      if (phase === "in") {
        node.style.transition = "none";
        node.style.opacity = "0";
        node.style.transform = hiddenTransform;
        return;
      }
      if (phase === "out") {
        node.style.transition = `opacity ${durationMs}ms ease, transform ${durationMs}ms ease`;
        node.style.opacity = "0";
        node.style.transform = hiddenTransform;
      }
    }

    function startInTransition(node, transition, baseTransform = "") {
      const phase = String(transition?.phase || "").trim().toLowerCase();
      const type = String(transition?.type || "CUT").trim().toUpperCase();
      const durationMs = Math.max(0, Math.round(Number(transition?.durationMs || 0)));
      const finalTransform = String(baseTransform || "").trim();
      if (phase !== "in" || durationMs <= 0 || type === "CUT") {
        node.style.transition = "";
        node.style.opacity = "1";
        node.style.transform = finalTransform;
        return;
      }
      const startedSig = `${String(node.dataset.transitionSig || "")}|started`;
      if (node.dataset.transitionStartedSig === startedSig) return;
      node.dataset.transitionStartedSig = startedSig;
      window.requestAnimationFrame(() => {
        node.style.transition = `opacity ${durationMs}ms ease, transform ${durationMs}ms ease`;
        node.style.opacity = "1";
        node.style.transform = finalTransform;
      });
    }

    function syncLayerNode(node, layer, layerIndex) {
      const asset = layer?.asset || null;
      const scene = layer?.scene || null;
      const kind = String(asset?.kind || "").toLowerCase();
      const src = assetUrlFor(String(asset?.id || ""), layer, kind);
      const state = String(layer?.state || "playing").toLowerCase();
      node.style.zIndex = String(Number(layer?.renderOrder || layerIndex + 1));
      applyTransitionToNode(node, layer?.transition, "");

      if (!asset?.id || !kind) {
        node.textContent = "";
        return;
      }

      const wantVideo = kind === "video";
      let media = node.firstElementChild;
      if (!media || (wantVideo && media.tagName !== "VIDEO") || (!wantVideo && media.tagName !== "IMG")) {
        node.textContent = "";
        media = document.createElement(wantVideo ? "video" : "img");
        if (wantVideo) {
          media.setAttribute("autoplay", "");
          media.setAttribute("playsinline", "");
          media.setAttribute("preload", "auto");
          media.autoplay = true;
          media.playsInline = true;
          media.preload = "auto";
        } else {
          media.setAttribute("alt", "");
        }
        node.appendChild(media);
      }

      const mediaClassName = String(mediaClassNameForLayer(layer, kind, layerIndex) || "").trim();
      if (mediaClassName) {
        const preserved = media.classList.contains("is-ready") ? ["is-ready"] : [];
        syncElementClasses(media, [mediaClassName, ...preserved]);
      } else {
        media.removeAttribute("class");
      }
      if (wantVideo) {
        const videoId = String(videoIdForLayer(layer, layerIndex) || "").trim();
        if (videoId) media.id = videoId;
        else media.removeAttribute("id");
      } else {
        media.removeAttribute("id");
      }

      if (wantVideo) {
        const shouldMute = !!scene?.mute || String(layer?.launchMode || "").trim().toLowerCase() === "embedded";
        media.loop = !!scene?.loop;
        media.defaultMuted = shouldMute;
        media.muted = shouldMute;
        if (shouldMute) media.setAttribute("muted", "");
        else media.removeAttribute("muted");
        const sourceChanged = media.getAttribute("src") !== src;
        if (sourceChanged) {
          media.setAttribute("src", src);
          try { media.load(); } catch (_) {}
        }
        media.oncanplay = () => {
          if (String(layer?.state || "playing").toLowerCase() === "paused") return;
          startInTransition(node, layer?.transition, "");
          media.play().catch(() => {});
        };
        media.onended = () => {
          if (scene?.loop) return;
          if (onVideoEnded) onVideoEnded(layer, layerIndex, media);
        };
        if (state === "paused") {
          try { media.pause(); } catch (_) {}
        } else {
          if (!sourceChanged && media.readyState >= 2) startInTransition(node, layer?.transition, "");
          media.play().catch(() => {});
        }
      } else {
        const sourceChanged = media.getAttribute("src") !== src;
        if (sourceChanged) media.setAttribute("src", src);
        media.onload = () => {
          startInTransition(node, layer?.transition, "");
        };
        if (!sourceChanged || media.complete) startInTransition(node, layer?.transition, "");
      }
    }

    function syncOverlayNode(node, ov, layer, overlayIndex, layerIndex, overlayValues, fontScale) {
      const ovType = normalizeOverlayType(ov?.type);
      if (!ovType) return false;
      const isImage = ovType === "image";
      const textAlign = normalizeTextAlign(ov?.textAlign);
      const justify = textAlign === "left" ? "flex-start" : (textAlign === "right" ? "flex-end" : "center");
      const fx = textEffectStyles(ovType, ov?.textEffects, ov?.color);
      const bg = String(ov?.bgColor || "transparent").trim() || "transparent";
      const rotateDeg = Number(ov?.rotateDeg || 0);
      const scale = Number(ov?.scale || 1);
      const baseFontPx = Number(ov?.fontSizePx || 24);
      const resolvedFontScale = Number.isFinite(Number(fontScale)) ? Number(fontScale) : 1;
      const scaledFontPx = Math.max(1, baseFontPx * resolvedFontScale);
      const overlayZ = Number(ov?.zIndex || overlayIndex + 1);
      const stackZ = Number(layer?.renderOrder || layerIndex + 1) * 1000 + overlayZ;

      setNodeClasses(node, [overlayClassName, isImage ? overlayImageLayerClassName : "", ovType === "text" ? overlayTextLayerClassName : ""]);

      const layoutSig = [
        Number(ov?.xPct || 0),
        Number(ov?.yPct || 0),
        Number(ov?.wPct || 20),
        Number(ov?.hPct || 8),
        Number(ov?.opacity ?? 1),
        String(ov?.color || "#ffffff"),
        isImage ? "transparent" : bg,
        textAlign,
        justify,
        fx.fontWeight,
        fx.fontStyle,
        fx.textTransform,
        fx.letterSpacing,
        fx.textDecoration,
        fx.textShadow,
        scaledFontPx,
        String(ov?.fontFamily || "").replaceAll(";", ""),
        rotateDeg,
        scale,
        stackZ,
      ].join("|");

      if (node.dataset.layoutSig !== layoutSig) {
        node.style.left = `${Number(ov?.xPct || 0)}%`;
        node.style.top = `${Number(ov?.yPct || 0)}%`;
        node.style.width = `${Number(ov?.wPct || 20)}%`;
        node.style.height = `${Number(ov?.hPct || 8)}%`;
        node.style.transform = `rotate(${rotateDeg}deg) scale(${scale})`;
        node.style.opacity = `${Number(ov?.opacity ?? 1)}`;
        node.style.color = String(ov?.color || "#ffffff");
        node.style.background = isImage ? "transparent" : bg;
        node.style.textAlign = textAlign;
        node.style.justifyContent = justify;
        node.style.fontWeight = fx.fontWeight;
        node.style.fontStyle = fx.fontStyle;
        node.style.textTransform = fx.textTransform;
        node.style.letterSpacing = fx.letterSpacing;
        node.style.textDecoration = fx.textDecoration;
        node.style.textShadow = fx.textShadow;
        node.style.fontSize = `${scaledFontPx}px`;
        node.style.fontFamily = String(ov?.fontFamily || "").replaceAll(";", "") || "inherit";
        node.style.zIndex = `${stackZ}`;
        node.dataset.layoutSig = layoutSig;
      }
      applyTransitionToNode(node, layer?.transition, node.style.transform || "");

      if (isImage) {
        const ovAssetId = String(ov?.assetId || "").trim();
        if (ovAssetId) {
          const fitSafe = sanitizeFit(ov?.fit);
          const ovSrc = assetUrlFor(ovAssetId, layer, ovType);
          const contentSig = `${ovType}|${ovAssetId}|${fitSafe}`;
          let img = node.querySelector("img");
          if (!(img instanceof HTMLImageElement)) {
            node.textContent = "";
            img = document.createElement("img");
            img.alt = "";
            node.appendChild(img);
          }
          img.className = imageClassName;
          if (img.getAttribute("src") !== ovSrc) img.setAttribute("src", ovSrc);
          if (img.style.objectFit !== fitSafe) img.style.objectFit = fitSafe;
          node.dataset.contentSig = contentSig;
        } else if (node.dataset.contentSig !== "empty") {
          node.textContent = "";
          node.dataset.contentSig = "empty";
        }
      } else {
        const text = overlayTextFor(ov, overlayValues, layer, overlayIndex, layerIndex);
        let textEl = node.querySelector(".media-preview-overlay-text-content");
        if (!(textEl instanceof HTMLElement)) {
          node.textContent = "";
          textEl = document.createElement("span");
          textEl.className = "media-preview-overlay-text-content";
          node.appendChild(textEl);
        }
        if (node.dataset.contentSig !== "text" || node.dataset.textVal !== text) {
          textEl.textContent = text;
          node.dataset.contentSig = "text";
          node.dataset.textVal = text;
        }
        fitTextOverlayNode(node, scaledFontPx);
      }

      if (decorateOverlayNode) {
        decorateOverlayNode(node, {
          overlay: ov,
          layer,
          overlayIndex,
          layerIndex,
          overlayType: ovType,
          textAlign,
        });
      }
      return true;
    }

    function render(payload) {
      const layers = Array.isArray(payload?.layers) ? payload.layers : [];
      const overlayValues = payload?.overlayValues || {};
      const fontScale = payload?.fontScale ?? 1;

      if (layersRoot) {
        const existingLayerNodes = new Map();
        [...layersRoot.querySelectorAll(`:scope > .${layerClassName.split(/\s+/).filter(Boolean)[0] || "media-layer"}`)]
          .forEach((node) => existingLayerNodes.set(node.getAttribute("data-layer-id"), node));
        layers.forEach((layer, layerIndex) => {
          const layerId = layerIdFor(layer, layerIndex);
          if (!layerId) return;
          let node = existingLayerNodes.get(layerId);
          if (!node) {
            node = document.createElement("div");
            node.className = layerClassName;
            node.setAttribute("data-layer-id", layerId);
            layersRoot.appendChild(node);
          }
          existingLayerNodes.delete(layerId);
          syncLayerNode(node, layer, layerIndex);
        });
        existingLayerNodes.forEach((node) => {
          try {
            const video = node.querySelector("video");
            if (video) {
              video.pause();
              video.removeAttribute("src");
            }
          } catch (_) {}
          node.remove();
        });
      }

      if (overlayRoot) {
        const overlays = [];
        layers.forEach((layer, layerIndex) => {
          if (String(layer?.state || "playing").toLowerCase() === "paused") return;
          const ovs = Array.isArray(layer?.scene?.overlays) ? layer.scene.overlays : [];
          ovs.forEach((ov, overlayIndex) => overlays.push({ ov, layer, overlayIndex, layerIndex }));
        });

        const existingOverlayNodes = new Map();
        [...overlayRoot.querySelectorAll(`:scope > .${overlayClassName.split(/\s+/).filter(Boolean)[0] || "media-scene-overlay"}`)]
          .forEach((node) => existingOverlayNodes.set(node.getAttribute("data-ov-id"), node));

        overlays.forEach(({ ov, layer, overlayIndex, layerIndex }) => {
          const ovId = overlayIdFor(ov, layer, overlayIndex, layerIndex);
          let node = existingOverlayNodes.get(ovId);
          if (!node) {
            node = document.createElement("div");
            node.setAttribute("data-ov-id", ovId);
            overlayRoot.appendChild(node);
          }
          existingOverlayNodes.delete(ovId);
          syncOverlayNode(node, ov, layer, overlayIndex, layerIndex, overlayValues, fontScale);
        });

        existingOverlayNodes.forEach((node) => node.remove());
      }
    }

    function clear() {
      if (layersRoot) layersRoot.textContent = "";
      if (overlayRoot) overlayRoot.textContent = "";
    }

    return { render, clear };
  }

  window.PinballctlMediaSceneRenderer = {
    createSceneRenderer,
    clamp,
    esc,
    normalizeOverlayType,
    normalizeTextAlign,
    normalizeTextEffects,
    textEffectStyles,
  };
})();
