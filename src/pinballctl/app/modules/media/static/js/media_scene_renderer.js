(() => {
  function clamp(v, lo, hi) {
    const n = Number(v);
    if (!Number.isFinite(n)) return lo;
    return Math.max(lo, Math.min(hi, n));
  }

  function normalizeTextAlign(raw) {
    const t = String(raw || "").trim().toLowerCase();
    return ["left", "center", "right"].includes(t) ? t : "center";
  }

  function normalizeLayerType(raw) {
    const t = String(raw || "").trim().toLowerCase();
    if (t === "badge") return "text";
    if (t === "frame") return "image";
    return ["text", "image", "video"].includes(t) ? t : "text";
  }

  function defaultAssetUrlBuilder(assetId) {
    return assetId ? `/api/media/assets/file/${encodeURIComponent(assetId)}` : "";
  }

  function defaultOverlayText(layer, values) {
    const key = String(layer?.valueKey || "").trim();
    if (key && values && Object.prototype.hasOwnProperty.call(values, key)) return String(values[key] ?? "");
    return String(layer?.text || "");
  }

  function fitText(node, fontPx) {
    if (!(node instanceof HTMLElement)) return;
    const textEl = node.querySelector(".media-preview-overlay-text-content");
    if (!(textEl instanceof HTMLElement)) return;
    let low = 8;
    let high = Math.max(8, Math.round(Number(fontPx || 24)));
    let best = low;
    const fits = () => textEl.scrollWidth <= node.clientWidth + 1 && textEl.scrollHeight <= node.clientHeight + 1;
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
    textEl.style.fontSize = `${best}px`;
  }

  function createSceneRenderer(options) {
    const layersRoot = options?.layersRoot || null;
    const overlayRoot = options?.overlayRoot || null;
    const root = overlayRoot || layersRoot || null;
    const overlayClassName = String(options?.overlayClassName || "media-preview-overlay");
    const overlayImageLayerClassName = String(options?.overlayImageLayerClassName || "");
    const overlayTextLayerClassName = String(options?.overlayTextLayerClassName || "");
    const imageClassName = String(options?.imageClassName || "media-preview-overlay-image");
    const assetUrlFor = typeof options?.assetUrlFor === "function" ? options.assetUrlFor : defaultAssetUrlBuilder;
    const overlayTextFor = typeof options?.overlayTextFor === "function" ? options.overlayTextFor : defaultOverlayText;
    const videoIdForLayer = typeof options?.videoIdForLayer === "function" ? options.videoIdForLayer : () => "";
    const decorateOverlayNode = typeof options?.decorateOverlayNode === "function" ? options.decorateOverlayNode : null;

    function render(payload) {
      if (!root) return;
      const visualLayers = Array.isArray(payload?.visualLayers) ? payload.visualLayers.slice() : [];
      const overlayValues = payload?.overlayValues || {};
      const fontScale = Number(payload?.fontScale || 1) || 1;
      const playbackState = String(payload?.playbackState || "paused").toLowerCase();
      const loop = !!payload?.loop;
      const mute = !!payload?.mute;

      visualLayers.sort((a, b) => Number(a?.zIndex || 0) - Number(b?.zIndex || 0));
      root.textContent = "";

      visualLayers.forEach((layer, idx) => {
        const type = normalizeLayerType(layer?.type);
        const node = document.createElement("div");
        node.className = [
          overlayClassName,
          type === "image" || type === "video" ? overlayImageLayerClassName : "",
          type === "text" ? overlayTextLayerClassName : "",
        ].filter(Boolean).join(" ");
        node.style.left = `${Number(layer?.xPct || 0)}%`;
        node.style.top = `${Number(layer?.yPct || 0)}%`;
        node.style.width = `${Number(layer?.wPct || 20)}%`;
        node.style.height = `${Number(layer?.hPct || 8)}%`;
        node.style.transform = `rotate(${Number(layer?.rotateDeg || 0)}deg) scale(${Number(layer?.scale || 1)})`;
        node.style.opacity = `${Number(layer?.opacity ?? 1)}`;
        node.style.zIndex = `${idx + 1}`;
        node.setAttribute("data-overlay-idx", String(idx));

        if (type === "text") {
          node.style.background = String(layer?.bgColor || "transparent");
          node.style.color = String(layer?.color || "#ffffff");
          node.style.textAlign = normalizeTextAlign(layer?.textAlign);
          const textEl = document.createElement("span");
          textEl.className = "media-preview-overlay-text-content";
          textEl.textContent = overlayTextFor(layer, overlayValues, null, idx, idx);
          textEl.style.fontFamily = String(layer?.fontFamily || "").trim() || "inherit";
          textEl.style.fontSize = `${Math.max(8, Number(layer?.fontSizePx || 24) * fontScale)}px`;
          node.appendChild(textEl);
          fitText(node, Math.max(8, Number(layer?.fontSizePx || 24) * fontScale));
        } else {
          const assetId = String(layer?.assetId || "").trim();
          const src = assetUrlFor(assetId, layer, type);
          if (type === "video") {
            const video = document.createElement("video");
            const videoId = String(videoIdForLayer(layer, idx) || "").trim();
            if (videoId) video.id = videoId;
            video.autoplay = true;
            video.playsInline = true;
            video.preload = "auto";
            video.loop = loop;
            video.muted = mute;
            video.defaultMuted = mute;
            video.className = "media-preview-base";
            video.src = src;
            if (playbackState === "paused") {
              video.addEventListener("loadedmetadata", () => {
                try {
                  video.pause();
                  video.currentTime = 0;
                } catch (_) {}
              }, { once: true });
            }
            node.appendChild(video);
          } else {
            const img = document.createElement("img");
            img.alt = "";
            img.className = [imageClassName, "media-preview-base"].filter(Boolean).join(" ");
            img.src = src;
            img.style.objectFit = String(layer?.fit || "contain");
            node.appendChild(img);
          }
        }

        root.appendChild(node);
        if (decorateOverlayNode) {
          decorateOverlayNode(node, {
            overlay: layer,
            overlayIndex: idx,
            layerIndex: idx,
            overlayType: type,
          });
        }
      });
    }

    function clear() {
      if (root) root.textContent = "";
    }

    return { render, clear };
  }

  window.PinballctlMediaSceneRenderer = {
    createSceneRenderer,
  };
})();
