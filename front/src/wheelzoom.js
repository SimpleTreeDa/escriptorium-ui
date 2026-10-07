/*
 * Usage:
 * var zoom = new WheelZoom(domElement)
 * zoom.register(container);
 */

"use strict";

/**
 * New position after zooming by `ratio` (new scale / old scale) around `point`,
 * given relative to the zoomed element's current top left corner: the point
 * under the cursor stays where it is.
 */
export function zoomedPosition(pos, point, ratio, round = (value) => value) {
    return {
        x: pos.x - round((point.x - point.x / ratio) * ratio),
        y: pos.y - round((point.y - point.y / ratio) * ratio),
    };
}

class zoomTarget {
    constructor(
        domElement,
        {
            map = false,
            mapScale = 0.2,
            mapColors = ["grey", "white"],
            mapMargin = 10,
            mapDuration = 2,
        },
    ) {
        // wrap the element in a container:
        var container = document.createElement("div");
        container.classList.add("js-wheelzoom-container");
        // disables right click menu
        container.addEventListener("contextmenu", function (e) {
            e.preventDefault();
        });
        // var rotationContainer = document.createElement('div');
        domElement.parentNode.insertBefore(container, domElement);
        container.appendChild(domElement);
        // rotationContainer.appendChild(domElement);
        // container.appendChild(rotationContainer);
        // rotationContainer.style.transformOrigin = 'center';
        container.style.position = "relative";
        container.style.overflow = "hidden";
        // container.style.width = '100%';
        // container.style.height = '100%';
        domElement.style.transformOrigin = "0 0";
        domElement.style.transition = "scale 0.3s";
        // domElement.style.display = 'block';
        domElement.classList.add("js-zoom-target");
        this.container = container;
        //this.rotationContainer = rotationContainer;
        this.element = domElement;

        this.map = map;
        if (this.map) {
            this.mapScale = mapScale;
            this.mapDuration = mapDuration;
            this.mapTimer = null;
            this.mapMargin = mapMargin;
            this.makeMap(mapMargin, mapColors);
            this.refreshMap();
        }
    }

    update(pos, scale) {
        this.element.style.transform =
            "translate(" +
            pos.x +
            "px," +
            pos.y +
            "px) " +
            "scale(" +
            scale +
            ")";
    }

    showMap(pos, scale) {
        if (this.map && scale > 1) {
            this.refreshMap();
            this.mapWhole.style.opacity = 0.7;
            this.mapCurrent.textContent = Math.round(scale * 100) + "%";
            this.mapCurrent.style.transform =
                "" +
                "translate(" +
                (-pos.x * this.mapScale) / scale +
                "px," +
                (-pos.y * this.mapScale) / scale +
                "px) " +
                "scale(" +
                1 / scale +
                ")";

            // fadeOut
            if (this.mapTimer) clearInterval(this.mapTimer);
            let nTicks = (this.mapDuration * 1000) / 100;
            let factor = this.mapWhole.style.opacity / nTicks;
            this.mapTimer = setInterval(
                function () {
                    if (this.mapWhole.style.opacity <= 0) {
                        clearInterval(this.mapTimer);
                    }
                    this.mapWhole.style.opacity =
                        this.mapWhole.style.opacity - factor;
                }.bind(this),
                100,
            );
        }
    }

    refreshMap() {
        if (this.map) {
            let bounds = this.container.getBoundingClientRect();
            this.mapWhole.style.top = bounds.y + this.mapMargin + "px";
            this.mapWhole.style.left = bounds.x + this.mapMargin + "px";
            this.mapWhole.style.width = bounds.width * this.mapScale + "px";
            this.mapWhole.style.height = bounds.height * this.mapScale + "px";
        }
    }

    makeMap(mapMargin, mapColors) {
        this.mapWhole = document.createElement("div");
        this.mapWhole.classList.add("wheelzoom-outter-map");
        this.mapWhole.style.position = "fixed";
        this.mapWhole.style.opacity = 0;
        this.mapWhole.style.backgroundColor = mapColors[0];
        this.mapWhole.style.pointerEvents = "none";
        this.container.appendChild(this.mapWhole);

        this.mapCurrent = document.createElement("div");
        this.mapCurrent.classList.add("wheelzoom-inner-map");
        this.mapCurrent.style.position = "absolute";
        this.mapCurrent.style.opacity = 0.5;
        this.mapCurrent.style.width = "100%";
        this.mapCurrent.style.height = "100%";
        this.mapCurrent.style.backgroundColor = mapColors[1];
        this.mapCurrent.style.transformOrigin = "0 0";
        this.mapWhole.appendChild(this.mapCurrent);
    }
}

// How far scrolling with two fingers on a touchpad moves the page, relative
// to how far the browser would scroll: the default, and the range to pick from.
export const PAN_SPEED = { default: 0.75, min: 0.25, max: 2 };

/**
 * A pan speed within PAN_SPEED's range, from a number or a string (as saved,
 * or from a range input), or the default one if it isn't a number.
 */
export function validPanSpeed(value) {
    const speed = typeof value === "string" ? parseFloat(value) : value;
    if (typeof speed !== "number" || !Number.isFinite(speed)) {
        return PAN_SPEED.default;
    }
    return Math.min(PAN_SPEED.max, Math.max(PAN_SPEED.min, speed));
}

export class WheelZoom {
    constructor({
        factor = 0.1,
        // see PAN_SPEED
        panSpeed = PAN_SPEED.default,
        minScale = 0.2,
        maxScale = 10,
        initialScale = 1,
        disabled = false,
        legacyModeEnabled = true,
        getActiveTool = () => {},
    } = {}) {
        this.factor = factor;
        this.panSpeed = panSpeed;
        this.minScale = minScale;
        this.maxScale = maxScale;
        this.initialScale = initialScale;
        this.disabled = disabled;
        this.legacyModeEnabled = legacyModeEnabled;
        this.getActiveTool = getActiveTool;
        // New UI: panels can have different widths, and each one fits the page to
        // its width. The position is then kept as a fraction of the panel width,
        // so that every panel shows the same part of the page. Use pixelPos() to
        // get it in pixels for a given panel.
        this.relative = !legacyModeEnabled;
        if (this.relative && typeof ResizeObserver !== "undefined") {
            // re-apply the position when a panel changes size, but not when a panel
            // leaves the page (closed, or while the next page loads): it is then 0x0
            this.resizeObserver = new ResizeObserver((entries) => {
                if (entries.some((e) => e.target.isConnected && e.contentRect.width > 0)) {
                    this.refresh();
                }
            });
        }

        // create a dummy tag for event bindings
        this.events = document.createElement("div");
        this.events.classList.add("wheelzoom-events-js");
        document.body.appendChild(this.events);

        this.targets = [];
        this.previousEvent = null;
        this.scale = this.initialScale;
        this.angle = 0;
        this.pos = { x: 0, y: 0 };
    }

    register(domElement, { mirror = false, map = false } = {}) {
        this.events.addEventListener("wheelzoom.reset", this.reset.bind(this));
        this.events.addEventListener(
            "wheelzoom.refresh",
            this.refresh.bind(this),
        );

        let target = new zoomTarget(domElement, { map: map });
        target.update(this.pixelPos(target), this.scale);
        this.targets.push(target);
        if (this.resizeObserver) this.resizeObserver.observe(target.container);
        if (!mirror) {
            // domElement.style.cursor = 'zoom-in';

            const scroll = function (event) {
                // looks like it breaks on some configurations?
                // if (event.altKey) return;  // supposed to move in history
                // (ctrl is not the browser zoom here: it is how browsers send
                // pinching on a touchpad)
                this.scrolling = target;
                this.scrolled.bind(this)(event);
            }
            const drag = function (event) {
                // in case of mask over the element, bc we bind to document so event.target can be whatever
                if (
                    (this.legacyModeEnabled || this.getActiveTool() !== "pan") &&
                    !(event.which === 3 || event.button === 2)
                ) {
                    return; // right click only
                }
                this.dragging = target;
                this.draggable.bind(this)(event);
            }

            // not passive, scrolled() prevents the browser's own scroll/zoom
            target.container.addEventListener("wheel", scroll.bind(this), {
                passive: false,
            });
            target.container.addEventListener("mousedown", drag.bind(this));
        } else {
            target.container.classList.add("mirror");
        }
        return target;
    }

    /**
     * Width that the position is relative to for this target: the width of its
     * panel, which the page is fitted to.
     */
    unitWidth(target) {
        return (this.relative && target && target.container.clientWidth) || 1;
    }

    /**
     * The position in pixels for this target.
     */
    pixelPos(target) {
        if (!this.relative) return this.pos;
        const width = this.unitWidth(target);
        return {
            x: Math.round(this.pos.x * width),
            y: Math.round(this.pos.y * width),
        };
    }

    /**
     * Convert a point or a distance in pixels in this target to the unit of the
     * position.
     */
    toUnits(point, target) {
        const width = this.unitWidth(target);
        return { x: point.x / width, y: point.y / width };
    }

    zoomTo(target, delta) {
        // target: the point to zoom around, in the unit of the position
        var oldScale = this.scale;
        this.scale *= Math.exp(delta);
        if (this.minScale !== null)
            this.scale = Math.max(this.minScale, this.scale);
        if (this.maxScale !== null)
            this.scale = Math.min(this.maxScale, this.scale);

        var diff = { scale: this.scale / oldScale };
        // fractions of a width can't be rounded, pixels are
        this.pos = zoomedPosition(
            this.pos, target, diff.scale, this.relative ? undefined : Math.round,
        );

        this.updateStyle(diff);
        for (let itarget of this.targets) {
            itarget.showMap(this.pixelPos(itarget), this.scale);
        }
        return diff;
    }

    zoomIn() {
        this.zoomTo(this.centerPoint(), 0.1);
    }

    zoomOut() {
        this.zoomTo(this.centerPoint(), -0.1);
    }

    centerPoint() {
        // closed panels stay registered: use the first one still on the page
        var first = this.targets.find((t) => t.container.isConnected) || this.targets[0];
        var tr = first.element.getBoundingClientRect();
        var center = this.toUnits({ x: tr.width / 2, y: tr.height / 2 }, first);
        return {
            x: center.x - this.pos.x,
            y: center.y - this.pos.y,
        };
    }

    /**
     * Whether a wheel event comes from a mouse wheel rather than from scrolling
     * with two fingers on a touchpad. Browsers don't tell, so this goes by what
     * they send for each.
     */
    isMouseWheel(e) {
        // Firefox scrolls by lines (or pages) for a mouse wheel
        if (e.deltaMode !== 0) return true;
        // touchpads also scroll sideways
        if (e.deltaX !== 0) return false;
        if (e.wheelDeltaY) {
            // Chromium and Safari: a touchpad's legacy delta is -3 times its
            // delta, a mouse wheel's is a number of notches of 120
            if (e.wheelDeltaY === -3 * e.deltaY) return false;
            return e.wheelDeltaY % 120 === 0;
        }
        // else a mouse wheel scrolls by big steps, a touchpad by small ones
        return Number.isInteger(e.deltaY) && Math.abs(e.deltaY) >= 50;
    }

    scrolled(e) {
        if (this.disabled) return null;
        e.preventDefault();

        // a touchpad gesture is a stream of events (with more of them after
        // the fingers leave, with momentum): handle them all the same way
        const time = e.timeStamp ?? Date.now();
        const mouse =
            this.lastWheel && time - this.lastWheel.time < 200
                ? this.lastWheel.mouse
                : this.isMouseWheel(e);
        this.lastWheel = { time, mouse };

        if (!e.ctrlKey && !mouse) {
            // scrolling with two fingers on a touchpad
            return this.panBy(
                -e.deltaX * this.panSpeed,
                -e.deltaY * this.panSpeed,
                this.scrolling,
            );
        }

        // a mouse wheel zooms a step for each notch, while pinching on a
        // touchpad (which browsers send as wheel events with ctrl) zooms as
        // much as the fingers moved
        const delta = mouse
            ? -Math.sign(e.deltaY) * this.factor
            : Math.max(-1, Math.min(1, -e.deltaY / 100));
        // determine the point on where the slide is zoomed in
        let bounds = e.target.getBoundingClientRect();
        var zoom_point = this.toUnits({
            x: e.pageX - bounds.x - document.documentElement.scrollLeft,
            y: e.pageY - bounds.y - document.documentElement.scrollTop,
        }, this.scrolling);

        return this.zoomTo(zoom_point, delta);
    }

    panBy(x, y, target) {
        // move the page by (x, y) pixels in target
        const oldPos = { x: this.pos.x, y: this.pos.y };
        const moved = this.toUnits({ x, y }, target);
        this.pos.x += moved.x;
        this.pos.y += moved.y;
        this.keepInView(target);
        const diff = {
            x: (this.pos.x - oldPos.x) / this.scale,
            y: (this.pos.y - oldPos.y) / this.scale,
            angle: 0,
        };
        this.updateStyle(diff);
        target.showMap(this.pixelPos(target), this.scale);
        return diff;
    }

    drag(e) {
        if (this.disabled) return null;
        e.preventDefault();
        var target = this.dragging;
        if (!target) return null;
        var oldPos = { x: this.pos.x, y: this.pos.y },
            oldAngle = this.angle;

        if (this.previousEvent) {
            if (e.altKey) {
                this.angle =
                    (this.angle + (e.pageX - this.previousEvent.pageX)) % 360;
            } else {
                const moved = this.toUnits({
                    x: e.pageX - this.previousEvent.pageX,
                    y: e.pageY - this.previousEvent.pageY,
                }, target);
                this.pos.x += moved.x;
                this.pos.y += moved.y;
            }
        }
        this.keepInView(target);
        this.previousEvent = e;
        let diff = {
            x: (this.pos.x - oldPos.x) / this.scale,
            y: (this.pos.y - oldPos.y) / this.scale,
            angle: this.angle - oldAngle,
        };
        this.updateStyle(diff);
        this.dragging.showMap(this.pixelPos(this.dragging), this.scale);
        return diff;
    }

    keepInView(target) {
        // Make sure the slide stays in its container area when zooming in/out
        if (this.legacyModeEnabled) {
            // disabled on new UI. there's a reset zoom button for this!
            var ts = target.container.getBoundingClientRect();
            var ter = target.element.getBoundingClientRect();
            if (ter.width * this.scale > ts.width) {
                if (this.pos.x > 0) {
                    this.pos.x = 0;
                }
                if (this.pos.x + ter.width < ts.width) {
                    this.pos.x = ts.width - ter.width;
                }
            } else {
                if (this.pos.x < 0) {
                    this.pos.x = 0;
                }
                if (this.pos.x + ter.width > ts.width) {
                    this.pos.x = ts.width - ter.width;
                }
            }
            if (ter.height * this.scale > ts.height) {
                if (this.pos.y > 0) {
                    this.pos.y = 0;
                }
                if (this.pos.y + ter.height < ts.height) {
                    this.pos.y = ts.height - ter.height;
                }
            } else {
                if (this.pos.y < 0) {
                    this.pos.y = 0;
                }
                if (this.pos.y + ter.height > ts.height) {
                    this.pos.y = ts.height - ter.height;
                }
            }
        }
    }

    removeDrag() {
        // this.targets.forEach(function(target,i) {
        //     target.element.classList.remove('notransition');
        // });

        document.removeEventListener("mouseup", this.bRemDrag);
        document.removeEventListener("mousemove", this.bDrag);
        this.previousEvent = null;
    }

    draggable(event) {
        if (this.disabled) return;
        event.preventDefault();
        this.previousEvent = event;
        // this.rotationOrigin = e.point;

        // set bound event handlers
        this.bDrag = this.drag.bind(this);
        this.bRemDrag = this.removeDrag.bind(this);
        document.addEventListener("mousemove", this.bDrag);
        document.addEventListener("mouseup", this.bRemDrag);
    }

    updateStyle(delta) {
        this.targets.forEach(
            function (target, i) {
                target.update(this.pixelPos(target), this.scale);
                // if (this.rotationOrigin) {
                //     target.rotationContainer.style.transformOrigin = this.rotationOrigin.x+'px '+this.rotationOrigin.y+'px';
                //     target.rotationContainer.style.transform = 'rotate('+this.angle+'deg)';
                // }
            }.bind(this),
        );
        var event = new CustomEvent("wheelzoom.updated", {
            detail: { delta: delta, pos: this.pos, scale: this.scale },
        });
        if (this.events) this.events.dispatchEvent(event);
    }

    refresh() {
        this.updateStyle();
    }

    reset() {
        var oldPos = { x: this.pos.x, y: this.pos.y },
            oldAngle = this.angle;
        this.pos = { x: 0, y: 0 };
        this.scale = this.initialScale || 1;
        this.updateStyle({ x: -oldPos.x, y: -oldPos.y, scale: 1 / oldAngle });
    }

    disable() {
        this.disabled = true;
    }

    enable() {
        this.disabled = false;
    }

    destroy() {
        // TODO
    }
}
