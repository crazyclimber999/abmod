/*

	This file is part of OpenWebRX,
	an open-source SDR receiver software with a web UI.
	Copyright (c) 2013-2015 by Andras Retzler <randras@sdr.hu>
	Copyright (c) 2019-2021 by Jakob Ketterl <dd5jfk@darc.de>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

*/

is_firefox = navigator.userAgent.indexOf("Firefox") >= 0;

var bandwidth;
var center_freq;
var fft_size;
var fft_compression = "none";
// La compressione dell audio serve anche al rivelatore di subtono, e quella
// di openwebrx e dichiarata con var dentro il gestore della configurazione,
// quindi invisibile da qui. Questa e sua.
var ctcssCompression = "none";
var fft_codec;
var waterfall_setup_done = 0;
var secondary_fft_size;

function updateVolume() {
    audioEngine.setVolume(parseFloat($("#openwebrx-panel-volume").val()) / 100);
}

function toggleMute() {
    var $muteButton = $('.openwebrx-mute-button');
    var $volumePanel = $('#openwebrx-panel-volume');
    if ($muteButton.hasClass('muted')) {
        $muteButton.removeClass('muted');
        $volumePanel.prop('disabled', false).val(volumeBeforeMute);
    } else {
        $muteButton.addClass('muted');
        volumeBeforeMute = $volumePanel.val();
        $volumePanel.prop('disabled', true).val(0);
    }

    updateVolume();
}

function zoomInOneStep() {
    zoom_set(zoom_level + 1);
}

function zoomOutOneStep() {
    zoom_set(zoom_level - 1);
}

function zoomInTotal() {
    zoom_set(zoom_levels.length - 1);
}

function zoomOutTotal() {
    zoom_set(0);
}

var waterfall_min_level;
var waterfall_max_level;
var waterfall_min_level_default;
var waterfall_max_level_default;
var waterfall_colors = buildWaterfallColors(['#000', '#FFF']);
var waterfall_auto_levels;
var waterfall_auto_min_range;

function buildWaterfallColors(input) {
    return chroma.scale(input).colors(256, 'rgb')
}

function updateWaterfallColors(which) {
    var $wfmax = $("#openwebrx-waterfall-color-max");
    var $wfmin = $("#openwebrx-waterfall-color-min");
    waterfall_max_level = parseInt($wfmax.val());
    waterfall_min_level = parseInt($wfmin.val());
    if (waterfall_min_level >= waterfall_max_level) {
        if (!which) {
            waterfall_min_level = waterfall_max_level -1;
        } else {
            waterfall_max_level = waterfall_min_level + 1;
        }
    }
    updateWaterfallSliders();
}

function updateWaterfallSliders() {
    $('#openwebrx-waterfall-color-max')
        .val(waterfall_max_level)
        .attr('title', 'Waterfall maximum level (' + Math.round(waterfall_max_level) + ' dB)');
    $('#openwebrx-waterfall-color-min')
        .val(waterfall_min_level)
        .attr('title', 'Waterfall minimum level (' + Math.round(waterfall_min_level) + ' dB)');
}

function waterfallColorsDefault() {
    waterfall_min_level = waterfall_min_level_default;
    waterfall_max_level = waterfall_max_level_default;
    updateWaterfallSliders();
    waterfallColorsContinuousReset();
}

function waterfallColorsAuto(levels) {
    var min_level = levels.min - waterfall_auto_levels.min;
    var max_level = levels.max + waterfall_auto_levels.max;
    max_level = Math.max(min_level + (waterfall_auto_min_range || 0), max_level);
    waterfall_min_level = min_level;
    waterfall_max_level = max_level;
    updateWaterfallSliders();
}

var waterfall_continuous = {
    min: -150,
    max: 0
};

function waterfallColorsContinuousReset() {
    waterfall_continuous.min = waterfall_min_level;
    waterfall_continuous.max = waterfall_max_level;
}

function waterfallColorsContinuous(levels) {
    if (levels.max > waterfall_continuous.max + 1) {
        waterfall_continuous.max += 1;
    } else if (levels.max < waterfall_continuous.max - 1) {
        waterfall_continuous.max -= .1;
    }
    if (levels.min < waterfall_continuous.min - 1) {
        waterfall_continuous.min -= 1;
    } else if (levels.min > waterfall_continuous.min + 1) {
        waterfall_continuous.min += .1;
    }
    waterfallColorsAuto(waterfall_continuous);
}

function setSmeterRelativeValue(value) {
    if (value < 0) value = 0;
    if (value > 1.0) value = 1.0;
    var $meter = $("#openwebrx-smeter");
    var $bar = $meter.find(".openwebrx-smeter-bar");
    $bar.css({transform: 'translate(' + ((value - 1) * 100) + '%) translateZ(0)'});
    if (value > 0.9) {
        // red
        $bar.css({background: 'linear-gradient(to top, #ff5939 , #961700)'});
    } else if (value > 0.7) {
        // yellow
        $bar.css({background: 'linear-gradient(to top, #fff720 , #a49f00)'});
    } else {
        // red
        $bar.css({background: 'linear-gradient(to top, #22ff2f , #008908)'});
    }
}

function setSquelchSliderBackground(val) {
    var $slider = $('#openwebrx-panel-receiver .openwebrx-squelch-slider');
    var min = Number($slider.attr('min'));
    var max = Number($slider.attr('max'));
    var sliderPosition = $slider.val();
    var relative = (val - min) / (max - min);
    // use a brighter color when squelch is open
    var color = val >= sliderPosition ? '#22ff2f' : '#008908';
    // we don't use the gradient, but separate the colors discretely using css tricks
    var style = 'linear-gradient(90deg, ' + color + ', ' + color + ' ' + relative * 100 + '%, #B6B6B6 ' + relative * 100 + '%)';
    $slider.css('--track-background', style);
}

function getLogSmeterValue(value) {
    return 10 * Math.log10(value);
}

function setSmeterAbsoluteValue(value) //the value that comes from `csdr squelch_and_smeter_cc`
{
    var logValue = getLogSmeterValue(value);
    setSquelchSliderBackground(logValue);
    var lowLevel = waterfall_min_level - 20;
    var highLevel = waterfall_max_level + 20;
    var percent = (logValue - lowLevel) / (highLevel - lowLevel);
    setSmeterRelativeValue(percent);
    $("#openwebrx-smeter-db").html(logValue.toFixed(1) + " dB");
}

function typeInAnimation(element, timeout, what, onFinish) {
    if (!what) {
        onFinish();
        return;
    }
    element.innerHTML += what[0];
    window.setTimeout(function () {
        typeInAnimation(element, timeout, what.substring(1), onFinish);
    }, timeout);
}


// ========================================================
// ================  DEMODULATOR ROUTINES  ================
// ========================================================

function getDemodulators() {
    return [
        $('#openwebrx-panel-receiver').demodulatorPanel().getDemodulator()
    ].filter(function(d) {
        return !!d;
    });
}

function mkenvelopes(visible_range) //called from mkscale
{
    var demodulators = getDemodulators();
    scale_ctx.clearRect(0, 0, scale_ctx.canvas.width, 22); //clear the upper part of the canvas (where filter envelopes reside)
    for (var i = 0; i < demodulators.length; i++) {
        demodulators[i].envelope.draw(visible_range);
    }
    if (demodulators.length) {
        var bandpass = demodulators[0].getBandpass();
        secondary_demod_waterfall_set_zoom(bandpass.low_cut, bandpass.high_cut);
    }
}

function waterfallWidth() {
    return $('body').width();
}


// ========================================================
// ===================  SCALE ROUTINES  ===================
// ========================================================

var scale_ctx;
var scale_canvas;

function scale_setup() {
    scale_canvas = $("#openwebrx-scale-canvas")[0];
    scale_ctx = scale_canvas.getContext("2d");
    scale_canvas.addEventListener("mousedown", scale_canvas_mousedown, false);
    scale_canvas.addEventListener("mousemove", scale_canvas_mousemove, false);
    scale_canvas.addEventListener("mouseup", scale_canvas_mouseup, false);
    resize_scale();
    var frequency_container = $("#openwebrx-frequency-container");
    frequency_container.on("mousemove", frequency_container_mousemove, false);
}

var scale_canvas_drag_params = {
    mouse_down: false,
    drag: false,
    start_x: 0,
    key_modifiers: {shiftKey: false, altKey: false, ctrlKey: false}
};

function scale_canvas_mousedown(evt) {
    scale_canvas_drag_params.mouse_down = true;
    scale_canvas_drag_params.drag = false;
    scale_canvas_drag_params.start_x = evt.pageX;
    scale_canvas_drag_params.key_modifiers.shiftKey = evt.shiftKey;
    scale_canvas_drag_params.key_modifiers.altKey = evt.altKey;
    scale_canvas_drag_params.key_modifiers.ctrlKey = evt.ctrlKey;
    evt.preventDefault();
}

function scale_offset_freq_from_px(x, visible_range) {
    if (typeof visible_range === "undefined") visible_range = get_visible_freq_range();
    return (visible_range.start + visible_range.bw * (x / waterfallWidth())) - center_freq;
}

function scale_canvas_mousemove(evt) {
    var event_handled = false;
    var i;
    var demodulators = getDemodulators();
    if (scale_canvas_drag_params.mouse_down && !scale_canvas_drag_params.drag && Math.abs(evt.pageX - scale_canvas_drag_params.start_x) > canvas_drag_min_delta)
    //we can use the main drag_min_delta thing of the main canvas
    {
        scale_canvas_drag_params.drag = true;
        //call the drag_start for all demodulators (and they will decide if they're dragged, based on X coordinate)
        for (i = 0; i < demodulators.length; i++) event_handled |= demodulators[i].envelope.drag_start(evt.pageX, scale_canvas_drag_params.key_modifiers);
        scale_canvas.style.cursor = "move";
    }
    else if (scale_canvas_drag_params.drag) {
        //call the drag_move for all demodulators (and they will decide if they're dragged)
        for (i = 0; i < demodulators.length; i++) event_handled |= demodulators[i].envelope.drag_move(evt.pageX);
        if (!event_handled) demodulators[0].set_offset_frequency(scale_offset_freq_from_px(evt.pageX));
    }

}

function frequency_container_mousemove(evt) {
    var frequency = center_freq + scale_offset_freq_from_px(evt.pageX);
    $('#openwebrx-panel-receiver').demodulatorPanel().setMouseFrequency(frequency);
}

function scale_canvas_end_drag(x) {
    scale_canvas.style.cursor = "default";
    scale_canvas_drag_params.drag = false;
    scale_canvas_drag_params.mouse_down = false;
    var event_handled = false;
    var demodulators = getDemodulators();
    for (var i = 0; i < demodulators.length; i++) event_handled |= demodulators[i].envelope.drag_end();
    if (!event_handled) demodulators[0].set_offset_frequency(scale_offset_freq_from_px(x));
}

function scale_canvas_mouseup(evt) {
    scale_canvas_end_drag(evt.pageX);
}

function scale_px_from_freq(f, range) {
    return Math.round(((f - range.start) / range.bw) * waterfallWidth());
}

function get_visible_freq_range() {
    if (!bandwidth) return false;
    var fcalc = function (x) {
        var canvasWidth = waterfallWidth() * zoom_levels[zoom_level];
        return Math.round(((-zoom_offset_px + x) / canvasWidth) * bandwidth) + (center_freq - bandwidth / 2);
    };
    var out = {
        start: fcalc(0),
        center: fcalc(waterfallWidth() / 2),
        end: fcalc(waterfallWidth()),
    }
    out.bw = out.end - out.start;
    out.hps = out.bw / waterfallWidth();
    return out;
}

var scale_markers_levels = [
    {
        "large_marker_per_hz": 10000000, //large
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 0
    },
    {
        "large_marker_per_hz": 5000000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 0
    },
    {
        "large_marker_per_hz": 1000000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 0
    },
    {
        "large_marker_per_hz": 500000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 1
    },
    {
        "large_marker_per_hz": 100000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 1
    },
    {
        "large_marker_per_hz": 50000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 2
    },
    {
        "large_marker_per_hz": 10000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 2
    },
    {
        "large_marker_per_hz": 5000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 3
    },
    {
        "large_marker_per_hz": 1000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 1
    }
];
var scale_min_space_bw_texts = 50;
var scale_min_space_bw_small_markers = 7;

function get_scale_mark_spacing(range) {
    var out = {};
    var fcalc = function (freq) {
        out.numlarge = (range.bw / freq);
        out.large = waterfallWidth() / out.numlarge; 	//distance between large markers (these have text)
        out.ratio = 5; 														//(ratio-1) small markers exist per large marker
        out.small = out.large / out.ratio; 								//distance between small markers
        if (out.small < scale_min_space_bw_small_markers) return false;
        if (out.small / 2 >= scale_min_space_bw_small_markers && freq.toString()[0] !== "5") {
            out.small /= 2;
            out.ratio *= 2;
        }
        out.smallbw = freq / out.ratio;
        return true;
    };
    for (var i = scale_markers_levels.length - 1; i >= 0; i--) {
        var mp = scale_markers_levels[i];
        if (!fcalc(mp.large_marker_per_hz)) continue;
        //console.log(mp.large_marker_per_hz);
        //console.log(out);
        if (out.large - mp.estimated_text_width > scale_min_space_bw_texts) break;
    }
    out.params = mp;
    return out;
}

var range;

function mkscale() {
    //clear the lower part of the canvas (where frequency scale resides; the upper part is used by filter envelopes):
    range = get_visible_freq_range();
    if (!range) return;
    mkenvelopes(range); //when scale changes we will always have to redraw filter envelopes, too
    scale_ctx.clearRect(0, 22, scale_ctx.canvas.width, scale_ctx.canvas.height - 22);
    scale_ctx.strokeStyle = "#fff";
    scale_ctx.font = "bold 11px sans-serif";
    scale_ctx.textBaseline = "top";
    scale_ctx.fillStyle = "#fff";
    var spacing = get_scale_mark_spacing(range);
    //console.log(spacing);
    var marker_hz = Math.ceil(range.start / spacing.smallbw) * spacing.smallbw;
    var text_h_pos = 22 + 10 + ((is_firefox) ? 3 : 0);
    var text_to_draw = '';
    var ftext = function (f) {
        text_to_draw = format_frequency(spacing.params.format, f, spacing.params.pre_divide, spacing.params.decimals);
    };
    var last_large;
    var x;
    while ((x = scale_px_from_freq(marker_hz, range)) <= window.innerWidth) {
        scale_ctx.beginPath();
        scale_ctx.moveTo(x, 22);
        if (marker_hz % spacing.params.large_marker_per_hz === 0) {  //large marker
            if (typeof first_large === "undefined") var first_large = marker_hz;
            last_large = marker_hz;
            scale_ctx.lineWidth = 3.5;
            scale_ctx.lineTo(x, 22 + 11);
            ftext(marker_hz);
            var text_measured = scale_ctx.measureText(text_to_draw);
            scale_ctx.textAlign = "center";
            //advanced text drawing begins
            if (zoom_level === 0 && (range.start + spacing.smallbw * spacing.ratio > marker_hz) && (x < text_measured.width / 2)) { //if this is the first overall marker when zoomed out...                  and if it would be clipped off the screen...
                if (scale_px_from_freq(marker_hz + spacing.smallbw * spacing.ratio, range) - text_measured.width >= scale_min_space_bw_texts) { //and if we have enough space to draw it correctly without clipping
                    scale_ctx.textAlign = "left";
                    scale_ctx.fillText(text_to_draw, 0, text_h_pos);
                }
            }
            else if (zoom_level === 0 && (range.end - spacing.smallbw * spacing.ratio < marker_hz) && (x > window.innerWidth - text_measured.width / 2)) { //     if this is the last overall marker when zoomed out...                 and if it would be clipped off the screen...
                if (window.innerWidth - text_measured.width - scale_px_from_freq(marker_hz - spacing.smallbw * spacing.ratio, range) >= scale_min_space_bw_texts) { //and if we have enough space to draw it correctly without clipping
                    scale_ctx.textAlign = "right";
                    scale_ctx.fillText(text_to_draw, window.innerWidth, text_h_pos);
                }
            }
            else scale_ctx.fillText(text_to_draw, x, text_h_pos); //draw text normally
        }
        else {  //small marker
            scale_ctx.lineWidth = 2;
            scale_ctx.lineTo(x, 22 + 8);
        }
        marker_hz += spacing.smallbw;
        scale_ctx.stroke();
    }
    if (zoom_level !== 0) { // if zoomed, we don't want the texts to disappear because their markers can't be seen
        // on the left side
        scale_ctx.textAlign = "center";
        var f = first_large - spacing.smallbw * spacing.ratio;
        x = scale_px_from_freq(f, range);
        ftext(f);
        var w = scale_ctx.measureText(text_to_draw).width;
        if (x + w / 2 > 0) scale_ctx.fillText(text_to_draw, x, 22 + 10);
        // on the right side
        f = last_large + spacing.smallbw * spacing.ratio;
        x = scale_px_from_freq(f, range);
        ftext(f);
        w = scale_ctx.measureText(text_to_draw).width;
        if (x - w / 2 < window.innerWidth) scale_ctx.fillText(text_to_draw, x, 22 + 10);
    }
}

function resize_scale() {
    var ratio = window.devicePixelRatio || 1;
    var w = window.innerWidth;
    var h = 47;
    scale_canvas.style.width = w + "px";
    scale_canvas.style.height = h + "px";
    w *= ratio;
    h *= ratio;
    scale_canvas.width = w;
    scale_canvas.height = h;
    scale_ctx.scale(ratio, ratio);
    mkscale();
    bookmarks.position();
}

function canvas_get_freq_offset(relativeX) {
    var rel = (relativeX / canvas_container.clientWidth);
    return Math.round((bandwidth * rel) - (bandwidth / 2));
}

function canvas_get_frequency(relativeX) {
    return center_freq + canvas_get_freq_offset(relativeX);
}


function format_frequency(format, freq_hz, pre_divide, decimals) {
    var out = format.replace("{x}", (freq_hz / pre_divide).toFixed(decimals));
    var at = out.indexOf(".") + 4;
    while (decimals > 3) {
        out = out.substr(0, at) + "," + out.substr(at);
        at += 4;
        decimals -= 3;
    }
    return out;
}

var canvas_drag = false;
var canvas_drag_min_delta = 1;
var canvas_mouse_down = false;
var canvas_drag_last_x;
var canvas_drag_last_y;
var canvas_drag_start_x;
var canvas_drag_start_y;

function canvas_mousedown(evt) {
    canvas_mouse_down = true;
    canvas_drag = false;
    canvas_drag_last_x = canvas_drag_start_x = evt.pageX;
    canvas_drag_last_y = canvas_drag_start_y = evt.pageY;
    evt.preventDefault(); //don't show text selection mouse pointer
}

function canvas_mousemove(evt) {
    if (!waterfall_setup_done) return;
    var relativeX = get_relative_x(evt);
    if (canvas_mouse_down) {
        if (!canvas_drag && Math.abs(evt.pageX - canvas_drag_start_x) > canvas_drag_min_delta) {
            canvas_drag = true;
            canvas_container.style.cursor = "move";
        }
        if (canvas_drag) {
            var deltaX = canvas_drag_last_x - evt.pageX;
            var dpx = range.hps * deltaX;
            if (
                !(zoom_center_rel + dpx > (bandwidth / 2 - waterfallWidth() * (1 - zoom_center_where) * range.hps)) &&
                !(zoom_center_rel + dpx < -bandwidth / 2 + waterfallWidth() * zoom_center_where * range.hps)
            ) {
                zoom_center_rel += dpx;
            }
            resize_canvases(false);
            canvas_drag_last_x = evt.pageX;
            canvas_drag_last_y = evt.pageY;
            mkscale();
            bookmarks.position();
        }
    } else {
        $('#openwebrx-panel-receiver').demodulatorPanel().setMouseFrequency(canvas_get_frequency(relativeX));
    }
}

function canvas_container_mouseleave() {
    canvas_end_drag();
}

function canvas_mouseup(evt) {
    if (!waterfall_setup_done) return;
    var relativeX = get_relative_x(evt);

    if (!canvas_drag) {
        $('#openwebrx-panel-receiver').demodulatorPanel().getDemodulator().set_offset_frequency(canvas_get_freq_offset(relativeX));
    }
    else {
        canvas_end_drag();
    }
    canvas_mouse_down = false;
}

function canvas_end_drag() {
    canvas_container.style.cursor = "crosshair";
    canvas_mouse_down = false;
}

function zoom_center_where_calc(screenposX) {
    return screenposX / waterfallWidth();
}

function get_relative_x(evt) {
    var relativeX = evt.offsetX || evt.layerX;
    if ($(evt.target).closest(canvas_container).length) return relativeX;
    // compensate for the frequency scale, since that is not resized by the browser.
    var relatives = $(evt.target).closest('#openwebrx-frequency-container').map(function(){
        return evt.pageX - this.offsetLeft;
    });
    if (relatives.length) relativeX = relatives[0];

    return relativeX - zoom_offset_px;
}

function canvas_mousewheel(evt) {
    if (!waterfall_setup_done) return;
    var relativeX = get_relative_x(evt);
    var dir = (evt.deltaY / Math.abs(evt.deltaY)) > 0;
    zoom_step(dir, relativeX, zoom_center_where_calc(evt.pageX));
    evt.preventDefault();
}


var zoom_max_level_hps = 33; //Hz/pixel
var zoom_levels_count = 14;

function get_zoom_coeff_from_hps(hps) {
    var shown_bw = (window.innerWidth * hps);
    return bandwidth / shown_bw;
}

var zoom_levels = [1];
var zoom_level = 0;
var zoom_offset_px = 0;
var zoom_center_rel = 0;
var zoom_center_where = 0;

var smeter_level = 0;

function mkzoomlevels() {
    zoom_levels = [1];
    var maxc = get_zoom_coeff_from_hps(zoom_max_level_hps);
    if (maxc < 1) return;
    // logarithmic interpolation
    var zoom_ratio = Math.pow(maxc, 1 / zoom_levels_count);
    for (var i = 1; i < zoom_levels_count; i++)
        zoom_levels.push(Math.pow(zoom_ratio, i));
}

function zoom_step(out, where, onscreen) {
    if ((out && zoom_level === 0) || (!out && zoom_level >= zoom_levels_count - 1)) return;
    if (out) --zoom_level;
    else ++zoom_level;

    zoom_center_rel = canvas_get_freq_offset(where);
    //console.log("zoom_step || zlevel: "+zoom_level.toString()+" zlevel_val: "+zoom_levels[zoom_level].toString()+" zoom_center_rel: "+zoom_center_rel.toString());
    zoom_center_where = onscreen;
    //console.log(zoom_center_where, zoom_center_rel, where);
    resize_canvases(true);
    mkscale();
    bookmarks.position();
}

function zoom_set(level) {
    if (!(level >= 0 && level <= zoom_levels.length - 1)) return;
    level = parseInt(level);
    zoom_level = level;
    //zoom_center_rel=canvas_get_freq_offset(-canvases[0].offsetLeft+waterfallWidth()/2); //zoom to screen center instead of demod envelope
    zoom_center_rel = $('#openwebrx-panel-receiver').demodulatorPanel().getDemodulator().get_offset_frequency();
    zoom_center_where = 0.5 + (zoom_center_rel / bandwidth); //this is a kind of hack
    resize_canvases(true);
    mkscale();
    bookmarks.position();
}

function zoom_calc() {
    var winsize = waterfallWidth();
    var canvases_new_width = winsize * zoom_levels[zoom_level];
    zoom_offset_px = -((canvases_new_width * (0.5 + zoom_center_rel / bandwidth)) - (winsize * zoom_center_where));
    if (zoom_offset_px > 0) zoom_offset_px = 0;
    if (zoom_offset_px < winsize - canvases_new_width)
        zoom_offset_px = winsize - canvases_new_width;
}

var networkSpeedMeasurement;
var currentprofile = {
    toString: function() {
        return this['sdr_id'] + '|' + this['profile_id'];
    }
};

var COMPRESS_FFT_PAD_N = 10; //should be the same as in csdr.c

/* ------------------------------------------------------------------ CTCSS */

/* Il subtono viene letto qui, dagli stessi campioni che vanno all'altoparlante.
   L'ADPCM va decodificato una seconda volta: AudioEngine tiene il suo decoder
   per se, e un secondo decoder sugli stessi byte costa pochissimo e si
   risincronizza da solo grazie ai marcatori SYNC che il server inserisce. */

var ctcssDetector = null;
var ctcssCodec = null;

function ctcssSpegni() {
    var $r = $('#openwebrx-ctcss');
    if ($r.length) $r.hide();
    if (ctcssDetector) ctcssDetector.clear();
}

/* La frequenza a cui si sta ascoltando: centro piu scostamento del
 * demodulatore. Serve solo per accorgersi che e cambiata. */
function ctcssSintonia() {
    try {
        var pannello = $('#openwebrx-panel-receiver').demodulatorPanel();
        var demod = (pannello && pannello.getDemodulator) ? pannello.getDemodulator() : null;
        var scostamento = (demod && demod.get_offset_frequency) ? demod.get_offset_frequency() : 0;
        if (typeof center_freq === 'undefined' || center_freq === null) return null;
        return center_freq + (scostamento || 0);
    } catch (e) {
        return null;
    }
}

function ctcssInit() {
    if (ctcssDetector || typeof CtcssDetector === 'undefined') return;
    ctcssDetector = new CtcssDetector(function(tono, margine) {
        var $r = $('#openwebrx-ctcss');
        var $v = $('#openwebrx-ctcss-value');
        if (!tono) {
            $v.html('&mdash;');
            $r.hide();
            return;
        }
        $v.html(tono.toFixed(1) + ' Hz <span class="ctcss-margine">(' +
                Math.round(margine) + 'x)</span>');
        $r.show();
        divlog('Sub-audible tone: ' + tono.toFixed(1) + ' Hz on ' +
               ((ctcssSintonia() || 0) / 1e6).toFixed(4) + ' MHz');
    });
    ctcssDetector.setTunedProbe(ctcssSintonia);
    if (typeof ImaAdpcmCodec !== 'undefined') ctcssCodec = new ImaAdpcmCodec();
    if (audioEngine && audioEngine.getOutputRate) {
        ctcssDetector.setSampleRate(audioEngine.getOutputRate());
    }
}

function ctcssFeed(data) {
    ctcssInit();
    if (!ctcssDetector) return;
    try {
        if (ctcssCompression === 'adpcm') {
            if (!ctcssCodec) return;
            ctcssDetector.push(ctcssCodec.decodeWithSync(new Uint8Array(data)));
        } else {
            ctcssDetector.push(new Int16Array(data));
        }
    } catch (e) {
        // un subtono mancato non deve mai fermare l'audio
    }
}

function on_ws_recv(evt) {
    if (typeof evt.data === 'string') {
        // text messages
        networkSpeedMeasurement.add(evt.data.length);

        if (evt.data.substr(0, 16) === "CLIENT DE SERVER") {
            params = Object.fromEntries(
                evt.data.slice(17).split(' ').map(function(param) {
                    var args = param.split('=');
                    return [args[0], args.slice(1).join('=')]
                })
            );
            var versionInfo = 'Unknown server';
            if (params.server && params.server === 'openwebrx' && params.version) {
                versionInfo = 'OpenWebRX version: ' + params.version;
            }
            divlog('Server acknowledged WebSocket connection, ' + versionInfo);
        } else {
            try {
                var json = JSON.parse(evt.data);
                switch (json.type) {
                    case "config":
                        var config = json['value'];
                        if ('waterfall_colors' in config)
                            waterfall_colors = buildWaterfallColors(config['waterfall_colors']);
                        if ('waterfall_levels' in config) {
                            waterfall_min_level_default = config['waterfall_levels']['min'];
                            waterfall_max_level_default = config['waterfall_levels']['max'];
                        }
                        if ('waterfall_auto_levels' in config)
                            waterfall_auto_levels = config['waterfall_auto_levels'];
                        if ('waterfall_auto_min_range' in config)
                            waterfall_auto_min_range = config['waterfall_auto_min_range'];
                        waterfallColorsDefault();

                        var initial_demodulator_params = {};
                        if ('start_mod' in config)
                            initial_demodulator_params['mod'] = config['start_mod'];
                        if ('start_offset_freq' in config)
                            initial_demodulator_params['offset_frequency'] = config['start_offset_freq'];
                        if ('initial_squelch_level' in config)
                            initial_demodulator_params['squelch_level'] = Number.isInteger(config['initial_squelch_level']) ? config['initial_squelch_level'] : -150;

                        if ('samp_rate' in config)
                            bandwidth = config['samp_rate'];
                        if ('center_freq' in config) {
                            center_freq = config['center_freq'];
                            // the box carries whatever unit the selector shows
                            var freq_unit = parseInt($('#openwebrx-freq-unit').val()) || 1000000;
                            $('#openwebrx-frequency-input').val(format_freq_value(center_freq, freq_unit));
                        }
                        if ('fft_size' in config) {
                            fft_size = config['fft_size'];
                            waterfall_clear();
                        }
                        if ('audio_compression' in config) {
                            var audio_compression = config['audio_compression'];
                            audioEngine.setCompression(audio_compression);
                            ctcssCompression = audio_compression;
                            divlog("Audio stream is " + ((audio_compression === "adpcm") ? "compressed" : "uncompressed") + ".");
                        }
                        if ('fft_compression' in config) {
                            fft_compression = config['fft_compression'];
                            divlog("FFT stream is " + ((fft_compression === "adpcm") ? "compressed" : "uncompressed") + ".");
                        }
                        if ('max_clients' in config)
                            $('#openwebrx-bar-clients').progressbar().setMaxClients(config['max_clients']);

                        waterfall_init();

                        var demodulatorPanel = $('#openwebrx-panel-receiver').demodulatorPanel();
                        demodulatorPanel.setCenterFrequency(center_freq);
                        demodulatorPanel.setInitialParams(initial_demodulator_params);
                        if ('squelch_auto_margin' in config)
                            demodulatorPanel.setSquelchMargin(config['squelch_auto_margin']);
                        bookmarks.loadLocalBookmarks();

                        if ('sdr_id' in config || 'profile_id' in config) {
                            currentprofile['sdr_id'] = config['sdr_id'] || currentprofile['sdr_id'];
                            currentprofile['profile_id'] = config['profile_id'] || currentprofile['profile_id'];
                            $('#openwebrx-sdr-profiles-listbox').val(currentprofile.toString());

                            waterfall_clear();
                        }

                        if ('tuning_precision' in config)
                            $('#openwebrx-panel-receiver').demodulatorPanel().setTuningPrecision(config['tuning_precision']);

                        break;
                    case "secondary_config":
                        var s = json['value'];
                        secondary_fft_size = s['secondary_fft_size'] || secondary_fft_size;
                        secondary_bw = s['secondary_bw'] || secondary_bw;
                        if_samp_rate = s['if_samp_rate'] || if_samp_rate;
                        if (if_samp_rate) secondary_demod_init_canvases();
                        break;
                    case "receiver_details":
                        $('.webrx-top-container').header().setDetails(json['value']);
                        break;
                    case "smeter":
                        smeter_level = json['value'];
                        setSmeterAbsoluteValue(smeter_level);
                        break;
                    case "cpuusage":
                        $('#openwebrx-bar-server-cpu').progressbar().setUsage(json['value']);
                        break;
                    case "clients":
                        $('#openwebrx-bar-clients').progressbar().setClients(json['value']);
                        break;
                    case "profiles":
                        var listbox = $("#openwebrx-sdr-profiles-listbox");
                        listbox.html(json['value'].map(function (profile) {
                            return '<option value="' + profile['id'] + '">' + profile['name'] + "</option>";
                        }).join(""));
                        $('#openwebrx-sdr-profiles-listbox').val(currentprofile.toString());
                        // this is a bit hacky since it only makes sense if the error is actually "no sdr devices"
                        // the only other error condition for which the overlay is used right now is "too many users"
                        // so there shouldn't be a problem here
                        if (Object.keys(json['value']).length) {
                            $('#openwebrx-error-overlay').hide();
                        }
                        break;
                    case "features":
                        Modes.setFeatures(json['value']);
                        break;
                    case "metadata":
                        $('.openwebrx-meta-panel').metaPanel().each(function(){
                            this.update(json['value']);
                        });
                        break;
                    case "dial_frequencies":
                        var as_bookmarks = json['value'].map(function (d) {
                            return {
                                name: d['mode'].toUpperCase(),
                                modulation: d['mode'],
                                frequency: d['frequency']
                            };
                        });
                        bookmarks.replace_bookmarks(as_bookmarks, 'dial_frequencies');
                        break;
                    case "bookmarks":
                        bookmarks.replace_bookmarks(json['value'], "server");
                        break;
                    case "sdr_error":
                        divlog(json['value'], true);
                        var $overlay = $('#openwebrx-error-overlay');
                        $overlay.find('.errormessage').text(json['value']);
                        $overlay.show();
                        $("#openwebrx-panel-receiver").demodulatorPanel().stopDemodulator();
                        break;
                    case "demodulator_error":
                        divlog(json['value'], true);
                        break;
                    case 'secondary_demod':
                        var value = json['value'];
                        var panels = [
                            $("#openwebrx-panel-wsjt-message").wsjtMessagePanel(),
                            $('#openwebrx-panel-packet-message').packetMessagePanel(),
                            $('#openwebrx-panel-pocsag-message').pocsagMessagePanel(),
                            $("#openwebrx-panel-js8-message").js8(),
                            $('#openwebrx-panel-5tone-message').fiveToneMessagePanel(),
                            $('#openwebrx-panel-2tone-message').twoToneMessagePanel()
                        ];
                        if (!panels.some(function(panel) {
                            if (!panel.supportsMessage(value)) return false;
                            panel.pushMessage(value);
                            return true;
                        })) {
                            secondary_demod_push_data(value);
                        }
                        break;
                    case 'log_message':
                        divlog(json['value'], true);
                        break;
                    case 'backoff':
                        divlog("Server is currently busy: " + json['reason'], true);
                        var $overlay = $('#openwebrx-error-overlay');
                        $overlay.find('.errormessage').text(json['reason']);
                        $overlay.show();
                        // set a higher reconnection timeout right away to avoid additional load
                        reconnect_timeout = 16000;
                        break;
                    case 'modes':
                        Modes.setModes(json['value']);
                        break;
                    case "bandplan_entries":
                        on_bandplan_received(json['value']);
                        break;
                    case "bandplan_result":
                        on_bandplan_result(json['value']);
                        break;
                    case "defaults_saved":
                        on_defaults_saved(json['value']);
                        break;
                    case "memories":
                        on_memories_received(json['value']);
                        break;
                    case "memory_saved":
                        on_memory_saved(json['value']);
                        break;
                    case "memory_deleted":
                        on_memory_deleted(json['value']);
                        break;
                    default:
                        console.warn('received message of unknown type: ' + json['type']);
                }
            } catch (e) {
                // don't lose exception
                console.error(e)
            }
        }
    } else if (evt.data instanceof ArrayBuffer) {
        // binary messages
        networkSpeedMeasurement.add(evt.data.byteLength);

        var type = new Uint8Array(evt.data, 0, 1)[0];
        var data = evt.data.slice(1);

        var waterfall_i16;
        var waterfall_f32;
        var i;

        switch (type) {
            case 1:
                // FFT data
                if (fft_compression === "none") {
                    waterfall_add(new Float32Array(data));
                } else if (fft_compression === "adpcm") {
                    fft_codec.reset();

                    waterfall_i16 = fft_codec.decode(new Uint8Array(data));
                    waterfall_f32 = new Float32Array(waterfall_i16.length - COMPRESS_FFT_PAD_N);
                    for (i = 0; i < waterfall_i16.length; i++) waterfall_f32[i] = waterfall_i16[i + COMPRESS_FFT_PAD_N] / 100;
                    waterfall_add(waterfall_f32);
                }
                break;
            case 2:
                // audio data
                audioEngine.pushAudio(data);
                ctcssFeed(data);
                break;
            case 3:
                // secondary FFT
                if (fft_compression === "none") {
                    secondary_demod_waterfall_add(new Float32Array(data));
                } else if (fft_compression === "adpcm") {
                    fft_codec.reset();

                    waterfall_i16 = fft_codec.decode(new Uint8Array(data));
                    waterfall_f32 = new Float32Array(waterfall_i16.length - COMPRESS_FFT_PAD_N);
                    for (i = 0; i < waterfall_i16.length; i++) waterfall_f32[i] = waterfall_i16[i + COMPRESS_FFT_PAD_N] / 100;
                    secondary_demod_waterfall_add(waterfall_f32);
                }
                break;
            case 4:
                // hd audio data
                audioEngine.pushHdAudio(data);
                break;
            default:
                console.warn('unknown type of binary message: ' + type)
        }
    }
}

var waterfall_measure_minmax_now = false;
var waterfall_measure_minmax_continuous = false;

function waterfall_measure_minmax_do(what) {
    // this is based on an oversampling factor of about 1,25
    var ignored = .1 * what.length;
    var data = what.slice(ignored, -ignored);
    return {
        min: Math.min.apply(Math, data),
        max: Math.max.apply(Math, data)
    };
}

function on_ws_opened() {
    $('#openwebrx-error-overlay').hide();
    ws.send("SERVER DE CLIENT client=openwebrx.js type=receiver");
    divlog("WebSocket opened to " + ws.url);
    if (!networkSpeedMeasurement) {
        networkSpeedMeasurement = new Measurement();
        networkSpeedMeasurement.report(60000, 1000, function(rate){
            $('#openwebrx-bar-network-speed').progressbar().setSpeed(rate);
        });
    } else {
        networkSpeedMeasurement.reset();
    }
    reconnect_timeout = false;
    ws.send(JSON.stringify({
        "type": "connectionproperties",
        "params": {
            "output_rate": audioEngine.getOutputRate(),
            "hd_output_rate": audioEngine.getHdOutputRate()
        }
    }));
}

var was_error = 0;

function divlog(what, is_error) {
    is_error = !!is_error;
    was_error |= is_error;
    if (is_error) {
        what = "<span class=\"webrx-error\">" + what + "</span>";
        toggle_panel("openwebrx-panel-log", true); //show panel if any error is present
    }
    $('#openwebrx-debugdiv')[0].innerHTML += what + "<br />";
    var nano = $('.nano');
    nano.nanoScroller();
    nano.nanoScroller({scroll: 'bottom'});
}

var volumeBeforeMute = 100.0;
var mute = false;

// Optimalise these if audio lags or is choppy:
var audio_buffer_maximal_length_sec = 1; //actual number of samples are calculated from sample rate

function onAudioStart(apiType){
    divlog('Web Audio API succesfully initialized, using ' + apiType  + ' API, sample rate: ' + audioEngine.getSampleRate() + " Hz");

    hideOverlay();

    // canvas_container is set after waterfall_init() has been called. we cannot initialize before.
    //if (canvas_container) synchronize_demodulator_init();

    //hide log panel in a second (if user has not hidden it yet)
    window.setTimeout(function () {
        toggle_panel("openwebrx-panel-log", !!was_error);
    }, 2000);

    //Synchronise volume with slider
    updateVolume();
}

var reconnect_timeout = false;

function on_ws_closed() {
    var demodulatorPanel = $("#openwebrx-panel-receiver").demodulatorPanel();
    demodulatorPanel.stopDemodulator();
    demodulatorPanel.resetInitialParams();
    if (reconnect_timeout) {
        // max value: roundabout 8 and a half minutes
        reconnect_timeout = Math.min(reconnect_timeout * 2, 512000);
    } else {
        // initial value: 1s
        reconnect_timeout = 1000;
    }
    divlog("WebSocket has closed unexpectedly. Attempting to reconnect in " + reconnect_timeout / 1000 + " seconds...", 1);

    setTimeout(open_websocket, reconnect_timeout);
}

function on_ws_error() {
    divlog("WebSocket error.", 1);
}

var ws;

function open_websocket() {
    var protocol = window.location.protocol.match(/https/) ? 'wss' : 'ws';

    var href = window.location.href;
    var index = href.lastIndexOf('/');
    if (index > 0) {
        href = href.substr(0, index + 1);
    }
    href = href.split("://")[1];
    href = protocol + "://" + href;
    if (!href.endsWith('/')) {
        href += '/';
    }
    var ws_url = href + "ws/";

    if (!("WebSocket" in window))
        divlog("Your browser does not support WebSocket, which is required for WebRX to run. Please upgrade to a HTML5 compatible browser.");
    ws = new WebSocket(ws_url);
    ws.onopen = on_ws_opened;
    ws.onmessage = on_ws_recv;
    ws.onclose = on_ws_closed;
    ws.binaryType = "arraybuffer";
    window.onbeforeunload = function () { //http://stackoverflow.com/questions/4812686/closing-websocket-correctly-html5-javascript
        ws.onclose = function () {
        };
        ws.close();
    };
    ws.onerror = on_ws_error;
}

function waterfall_mkcolor(db_value, waterfall_colors_arg) {
    waterfall_colors_arg = waterfall_colors_arg || waterfall_colors;
    var value_percent = (db_value - waterfall_min_level) / (waterfall_max_level - waterfall_min_level);
    value_percent = Math.max(0, Math.min(1, value_percent));

    var scaled = value_percent * (waterfall_colors_arg.length - 1);
    var index = Math.floor(scaled);
    var remain = scaled - index;
    if (remain === 0) return waterfall_colors_arg[index];
    return color_between(waterfall_colors_arg[index], waterfall_colors_arg[index + 1], remain);}

function color_between(first, second, percent) {
    return [
        first[0] + percent * (second[0] - first[0]),
        first[1] + percent * (second[1] - first[1]),
        first[2] + percent * (second[2] - first[2])
    ];
}


var canvas_context;
var canvases = [];
var canvas_default_height = 200;
var canvas_container;
var canvas_actual_line = -1;

function add_canvas() {
    var new_canvas = document.createElement("canvas");
    new_canvas.width = fft_size;
    new_canvas.height = canvas_default_height;
    canvas_actual_line = canvas_default_height;
    new_canvas.openwebrx_top = -canvas_default_height;
    new_canvas.style.transform = 'translate(0, ' + new_canvas.openwebrx_top.toString() + 'px)';
    canvas_context = new_canvas.getContext("2d");
    canvas_container.appendChild(new_canvas);
    canvases.push(new_canvas);
    while (canvas_container && canvas_container.clientHeight + canvas_default_height * 2 < canvases.length * canvas_default_height) {
        var c = canvases.shift();
        if (!c) break;
        canvas_container.removeChild(c);
    }
}


function init_canvas_container() {
    canvas_container = $("#webrx-canvas-container")[0];
    canvas_container.addEventListener("mouseleave", canvas_container_mouseleave, false);
    canvas_container.addEventListener("mousemove", canvas_mousemove, false);
    canvas_container.addEventListener("mouseup", canvas_mouseup, false);
    canvas_container.addEventListener("mousedown", canvas_mousedown, false);
    canvas_container.addEventListener("wheel", canvas_mousewheel, false);
    var frequency_container = $("#openwebrx-frequency-container");
    frequency_container.on("wheel", canvas_mousewheel, false);
}

canvas_maxshift = 0;

function shift_canvases() {
    canvases.forEach(function (p) {
        p.style.transform = 'translate(0, ' + (p.openwebrx_top++).toString() + 'px)';
    });
    canvas_maxshift++;
}

function resize_canvases(zoom) {
    if (typeof zoom === "undefined") zoom = false;
    if (!zoom) mkzoomlevels();
    zoom_calc();
    $('#webrx-canvas-container').css({
        width: waterfallWidth() * zoom_levels[zoom_level] + 'px',
        left: zoom_offset_px + "px"
    });
}

function waterfall_init() {
    init_canvas_container();
    resize_canvases();
    scale_setup();
    mkzoomlevels();
    waterfall_setup_done = 1;
}

function waterfall_add(data) {
    if (!waterfall_setup_done) return;
    var w = fft_size;

    if (waterfall_measure_minmax_now) {
        var levels = waterfall_measure_minmax_do(data);
        waterfall_measure_minmax_now = false;
        waterfallColorsAuto(levels);
        waterfallColorsContinuousReset();
    }

    if (waterfall_measure_minmax_continuous) {
        var level = waterfall_measure_minmax_do(data);
        waterfallColorsContinuous(level);
    }

    // create new canvas if the current one is full (or there isn't one)
    if (canvas_actual_line <= 0) add_canvas();

    //Add line to waterfall image
    var oneline_image = canvas_context.createImageData(w, 1);
    for (var x = 0; x < w; x++) {
        var color = waterfall_mkcolor(data[x]);
        for (i = 0; i < 3; i++) oneline_image.data[x * 4 + i] = color[i];
        oneline_image.data[x * 4 + 3] = 255;
    }

    //Draw image
    canvas_context.putImageData(oneline_image, 0, --canvas_actual_line);
    shift_canvases();
}

function waterfall_clear() {
    //delete all canvases
    while (canvases.length) {
        var x = canvases.shift();
        x.parentNode.removeChild(x);
    }
    canvas_actual_line = -1;
}

function openwebrx_resize() {
    resize_canvases();
    resize_scale();
}

function initProgressBars() {
    $(".openwebrx-progressbar").each(function(){
        var bar = $(this).progressbar();
        if ('setSampleRate' in bar) {
            bar.setSampleRate(audioEngine.getSampleRate());
        }
    })
}

function audioReporter(stats) {
    if (typeof(stats.buffersize) !== 'undefined') {
         $('#openwebrx-bar-audio-buffer').progressbar().setBuffersize(stats.buffersize);
    }

    if (typeof(stats.audioByteRate) !== 'undefined') {
        $('#openwebrx-bar-audio-speed').progressbar().setSpeed(stats.audioByteRate * 8);
    }

    if (typeof(stats.audioRate) !== 'undefined') {
        $('#openwebrx-bar-audio-output').progressbar().setAudioRate(stats.audioRate);
    }
}

var bookmarks;
var audioEngine;

// Everything here is built at runtime, never while the file is being evaluated:
// openwebrx.js is bundled BEFORE jQuery and before lib/MessagePanel.js, so at
// load time neither $ nor MessagePanel exists yet. Touching them up here threw
// a ReferenceError that aborted the rest of the bundle and broke the whole UI.
var TwoToneMessagePanel = null;

/*
 * Two-tone paging panel.
 *
 * Built at runtime for the same reason as the 5-tone one: openwebrx.js is
 * bundled BEFORE jQuery and MessagePanel, so anything at the top level that
 * touches either of them throws and kills the whole bundle, leaving the page
 * blank while still returning HTTP 200.
 */
function init_two_tone_panel_class() {
    if (TwoToneMessagePanel) return;

    TwoToneMessagePanel = function(el) {
        MessagePanel.call(this, el);
        this.initClearTimer();
    };

    TwoToneMessagePanel.prototype = new MessagePanel();

    TwoToneMessagePanel.prototype.supportsMessage = function(message) {
        return message['mode'] === '2tone';
    };

    TwoToneMessagePanel.prototype.render = function() {
        $(this.el).append($(
            '<div class="two-tone-rows">' +
                '<table>' +
                    '<thead><tr>' +
                        '<th class="time">Time</th>' +
                        '<th class="tones">Tones</th>' +
                        '<th class="plan">Plan</th>' +
                    '</tr></thead>' +
                    '<tbody></tbody>' +
                '</table>' +
            '</div>'
        ));
    };

    TwoToneMessagePanel.prototype.pushMessage = function(msg) {
        var $b = $(this.el).find('tbody');
        var ora = new Date().toISOString().slice(11, 19);

        // the measured frequencies are the result; the plan is only a label,
        // so a page that matches no known plan is still worth showing
        var toni = (msg.tone_a || 0).toFixed(1) + ' / ' + (msg.tone_b || 0).toFixed(1) + ' Hz';
        var piano = msg.plan ? msg.plan + ' ' + (msg.tone_numbers || '') : '-';
        var durate = 'held ' + (msg.duration_a || 0) + ' ms then ' + (msg.duration_b || 0) + ' ms';

        var $tr = $('<tr></tr>');
        $('<td class="time"></td>').text(ora).appendTo($tr);
        $('<td class="tones"></td>').text(toni).attr('title', durate).appendTo($tr);
        $('<td class="plan"></td>').text(piano).appendTo($tr);

        $b.append($tr);
        var $scroller = $(this.el).find('.two-tone-rows');
        if ($scroller.length) $scroller.scrollTop($scroller[0].scrollHeight);
    };

    $.fn.twoToneMessagePanel = function() {
        if (!this.data('panel')) {
            this.data('panel', new TwoToneMessagePanel(this));
        }
        return this.data('panel');
    };
}

var FiveToneMessagePanel = null;

function init_five_tone_panel_class() {
    if (FiveToneMessagePanel) return;

    FiveToneMessagePanel = function(el) {
        MessagePanel.call(this, el);
        this.initClearTimer();
    };

    FiveToneMessagePanel.prototype = new MessagePanel();

    FiveToneMessagePanel.prototype.supportsMessage = function(message) {
        return message['mode'] === '5tone';
    };

    FiveToneMessagePanel.prototype.standards =
        ['CCIR', 'ZVEI1', 'ZVEI2', 'DZVEI', 'EIA', 'CCITT'];

    FiveToneMessagePanel.prototype.enabledStandards = function() {
        // the choice is remembered per browser; by default everything is shown
        try {
            var stored = localStorage.getItem('5tone.standards');
            if (stored) return JSON.parse(stored);
        } catch (e) { /* private window or storage disabled */ }
        return this.standards.slice();
    };

    /* Il filtro per standard, in un posto solo: lo usano il clic sui pulsanti,
     * le righe nuove e il conteggio di quelle nascoste, che prima lo
     * ripetevano ognuno a modo suo. */
    FiveToneMessagePanel.prototype.matches = function(standard, sequence) {
        var attivi = this.enabledStandards();
        var std = String(standard || '').split('/');
        return std.some(function(x) { return attivi.indexOf(x) > -1; });
    };

    FiveToneMessagePanel.prototype.applyFilter = function() {
        var me = this;
        $(this.el).find('tbody tr').each(function() {
            $(this).toggle(me.matches($(this).data('standards'), $(this).find('.sequence').text()));
        });
        me.updateHiddenNote();
    };

    FiveToneMessagePanel.prototype.setEnabledStandards = function(list) {
        try {
            localStorage.setItem('5tone.standards', JSON.stringify(list));
        } catch (e) { /* not fatal: the filter still works for this session */ }
    };

    FiveToneMessagePanel.prototype.render = function() {
        var me = this;
        var attivi = this.enabledStandards();

        var $bar = $('<div class="five-tone-filter"></div>');
        this.standards.forEach(function(nome) {
            $('<button type="button"></button>')
                .text(nome)
                .toggleClass('active', attivi.indexOf(nome) > -1)
                .on('click', function() {
                    var $b = $(this);
                    $b.toggleClass('active');
                    var scelti = $bar.find('button.active').map(function() {
                        return $(this).text();
                    }).get();
                    me.setEnabledStandards(scelti);
                    // hide rows that no longer match, without losing them
                    me.applyFilter();
                })
                .appendTo($bar);
        });

        $(this.el).append($bar);
        // A sequence that arrives while its standard is switched off would
        // otherwise vanish without trace, and the panel looks broken rather
        // than filtered. This says so instead.
        $(this.el).append($('<div class="five-tone-hidden"></div>'));
        // the table is wrapped so the wrapper carries the scrollbar: scrolling
        // the tbody instead splits it from the thead and the column headers no
        // longer line up with their values
        $(this.el).append($(
            '<div class="five-tone-rows">' +
                '<table>' +
                    '<thead><tr>' +
                        '<th class="time">Time</th>' +
                        '<th class="sequence">Sequence</th>' +
                        '<th class="standard">Standard</th>' +
                    '</tr></thead>' +
                    '<tbody></tbody>' +
                '</table>' +
            '</div>'
        ));
    };

    FiveToneMessagePanel.prototype.updateHiddenNote = function() {
        var me = this;
        var nascoste = 0;
        $(this.el).find('tbody tr').each(function() {
            if (!me.matches($(this).data('standards'), $(this).find('.sequence').text())) nascoste++;
        });
        var $nota = $(this.el).find('.five-tone-hidden');
        if (!nascoste) {
            $nota.text('');
            return;
        }
        // kept to one line: the panel grows upward from the bottom of the
        // screen, so every extra line of this note moves the whole panel, and
        // the long version wrapped to two.
        $nota.text(nascoste + ' hidden by the filter above.');
    };

    FiveToneMessagePanel.prototype.pushMessage = function(msg) {
        var $b = $(this.el).find('tbody');
        var ora = new Date().toISOString().slice(11, 19);
        var standard = msg.standard || '';
        var visibile = this.matches(standard, msg.sequence || '');
        // the full names do not fit the column when a call matches several
        // standards, so the cell shows short codes and the title the full list
        var sigle = {CCIR: 'CC', ZVEI1: 'Z1', ZVEI2: 'Z2', DZVEI: 'DZ', EIA: 'EI', CCITT: 'CT'};
        var breve = standard.split('/').map(function(x) { return sigle[x] || x; }).join(' ');

        var $tr = $(
            '<tr>' +
                '<td class="time">' + ora + '</td>' +
                '<td class="sequence">' + this.htmlEscape(msg.sequence || '') + '</td>' +
                '<td class="standard" title="' + this.htmlEscape(standard) + '">' +
                    this.htmlEscape(breve) + '</td>' +
            '</tr>'
        );
        $tr.attr('data-standards', standard);
        if (!visibile) $tr.hide();
        $b.append($tr);
        this.updateHiddenNote();
        var $scroller = $(this.el).find('.five-tone-rows');
        if ($scroller.length) $scroller.scrollTop($scroller[0].scrollHeight);
    };

    $.fn.fiveToneMessagePanel = function() {
        if (!this.data('panel')) {
            this.data('panel', new FiveToneMessagePanel(this));
        }
        return this.data('panel');
    };
}

function openwebrx_init() {
    init_five_tone_panel_class();
    init_two_tone_panel_class();

    audioEngine = new AudioEngine(audio_buffer_maximal_length_sec, audioReporter);
    var $overlay = $('#openwebrx-autoplay-overlay');
    $overlay.on('click', function(){
        audioEngine.resume();
    });
    audioEngine.onStart(onAudioStart);
    if (!audioEngine.isAllowed()) {
        $('body').append($overlay);
        $overlay.show();
    }
    fft_codec = new ImaAdpcmCodec();
    initProgressBars();
    open_websocket();
    secondary_demod_init();
    digimodes_init();
    initPanels();
    $('#openwebrx-panel-receiver').demodulatorPanel();
    window.addEventListener("resize", openwebrx_resize);
    bookmarks = new BookmarkBar();
    initSliders();
}

function initSliders() {
    $('#openwebrx-panel-receiver').on('wheel', 'input[type=range]', function(ev){
        var $slider = $(this);
        if (!$slider.attr('step')) return;
        var val = Number($slider.val());
        var step = Number($slider.attr('step'));
        if (ev.originalEvent.deltaY > 0) {
            step *= -1;
        }
        $slider.val(val + step);
        $slider.trigger('change');
    });

    var waterfallAutoButton = $('#openwebrx-waterfall-colors-auto');
    waterfallAutoButton.on('click', function() {
        waterfall_measure_minmax_now=true;
    }).on('contextmenu', function(){
        waterfall_measure_minmax_continuous = !waterfall_measure_minmax_continuous;
        waterfallColorsContinuousReset();
        waterfallAutoButton[waterfall_measure_minmax_continuous ? 'addClass' : 'removeClass']('highlighted');
        $('#openwebrx-waterfall-color-min, #openwebrx-waterfall-color-max').prop('disabled', waterfall_measure_minmax_continuous);

        return false;
    });
}

function digimodes_init() {
    // initialze DMR timeslot muting
    $('.openwebrx-dmr-timeslot-panel').click(function (e) {
        $(e.currentTarget).toggleClass("muted");
        update_dmr_timeslot_filtering();
    // don't mute when the location icon is clicked
    }).find('.location').click(function(e) {
        e.stopPropagation();
    });

    $('.openwebrx-meta-panel').metaPanel();
}

function update_dmr_timeslot_filtering() {
    var filter = $('.openwebrx-dmr-timeslot-panel').map(function (index, el) {
        return (!$(el).hasClass("muted")) << index;
    }).toArray().reduce(function (acc, v) {
        return acc | v;
    }, 0);
    $('#openwebrx-panel-receiver').demodulatorPanel().getDemodulator().setDmrFilter(filter);
}

function hideOverlay() {
    var $overlay = $('#openwebrx-autoplay-overlay');
    $overlay.css('opacity', 0);
    $overlay.on('transitionend', function() {
        $overlay.hide();
    });
}

var rt = function (s, n) {
    return s.replace(/[a-zA-Z]/g, function (c) {
        return String.fromCharCode((c <= "Z" ? 90 : 122) >= (c = c.charCodeAt(0) + n) ? c : c - 26);
    });
};

// ========================================================
// =======================  PANELS  =======================
// ========================================================

function panel_displayed(el){
    return !(el.style && el.style.display && el.style.display === 'none') && !(el.movement && el.movement === 'collapse');
}

function toggle_panel(what, on) {
    var item = $('#' + what)[0];
    if (!item) return;
    var displayed = panel_displayed(item);
    if (typeof on !== "undefined" && displayed === on) {
        return;
    }
    if (displayed) {
        item.movement = 'collapse';
        item.style.transform = "perspective(600px) rotateX(90deg)";
        item.style.transitionProperty = 'transform';
    } else {
        item.movement = 'expand';
        item.style.display = null;
        setTimeout(function(){
            item.style.transitionProperty = 'transform';
            item.style.transform = 'perspective(600px) rotateX(0deg)';
        }, 20);
    }
    item.style.transitionDuration = "600ms";
    item.style.transitionDelay = "0ms";
}

function first_show_panel(panel) {
    panel.style.transitionDuration = 0;
    panel.style.transitionDelay = 0;
    var rotx = (Math.random() > 0.5) ? -90 : 90;
    var roty = 0;
    if (Math.random() > 0.5) {
        var rottemp = rotx;
        rotx = roty;
        roty = rottemp;
    }
    if (rotx !== 0 && Math.random() > 0.5) rotx = 270;
    panel.style.transform = "perspective(600px) rotateX(%1deg) rotateY(%2deg)"
        .replace("%1", rotx.toString()).replace("%2", roty.toString());
    window.setTimeout(function () {
        panel.style.transitionDuration = "600ms";
        panel.style.transitionDelay = (Math.floor(Math.random() * 500)).toString() + "ms";
        panel.style.transform = "perspective(600px) rotateX(0deg) rotateY(0deg)";
    }, 1);
}

function initPanels() {
    $('#openwebrx-panels-container').find('.openwebrx-panel').each(function(){
        var el = this;
        el.openwebrxPanelTransparent = (!!el.dataset.panelTransparent);
        el.addEventListener('transitionend', function(ev){
            if (ev.target !== el) return;
            el.style.transitionDuration = null;
            el.style.transitionDelay = null;
            el.style.transitionProperty = null;
            if (el.movement && el.movement === 'collapse') {
                el.style.display = 'none';
            }
            delete el.movement;
        });
        if (panel_displayed(el)) first_show_panel(el);
    });
}

/*
  _____  _       _                     _
 |  __ \(_)     (_)                   | |
 | |  | |_  __ _ _ _ __ ___   ___   __| | ___  ___
 | |  | | |/ _` | | '_ ` _ \ / _ \ / _` |/ _ \/ __|
 | |__| | | (_| | | | | | | | (_) | (_| |  __/\__ \
 |_____/|_|\__, |_|_| |_| |_|\___/ \__,_|\___||___/
            __/ |
           |___/
*/

var secondary_demod_fft_offset_db = 18; //need to calculate that later
var secondary_demod_canvases_initialized = false;
var secondary_demod_channel_freq = 1000;
var secondary_demod_waiting_for_set = false;
var secondary_demod_low_cut;
var secondary_demod_high_cut;
var secondary_demod_mousedown = false;
var secondary_demod_canvas_width;
var secondary_demod_canvas_left;
var secondary_demod_canvas_container;
var secondary_demod_current_canvas_actual_line;
var secondary_demod_current_canvas_context;
var secondary_demod_current_canvas_index;
var secondary_demod_canvases;
var secondary_bw = 31.25;
var if_samp_rate;

function secondary_demod_create_canvas() {
    var new_canvas = document.createElement("canvas");
    new_canvas.width = secondary_fft_size;
    new_canvas.height = $(secondary_demod_canvas_container).height();
    new_canvas.style.width = $(secondary_demod_canvas_container).width() + "px";
    new_canvas.style.height = $(secondary_demod_canvas_container).height() + "px";
    secondary_demod_current_canvas_actual_line = new_canvas.height - 1;
    $(secondary_demod_canvas_container).children().last().before(new_canvas);
    return new_canvas;
}

function secondary_demod_remove_canvases() {
    $(secondary_demod_canvas_container).children("canvas").remove();
}

function secondary_demod_init_canvases() {
    secondary_demod_remove_canvases();
    secondary_demod_canvases = [];
    secondary_demod_canvases.push(secondary_demod_create_canvas());
    secondary_demod_canvases.push(secondary_demod_create_canvas());
    secondary_demod_canvases[0].openwebrx_top = -$(secondary_demod_canvas_container).height();
    secondary_demod_canvases[1].openwebrx_top = 0;
    secondary_demod_canvases_update_top();
    secondary_demod_current_canvas_context = secondary_demod_canvases[0].getContext("2d");
    secondary_demod_current_canvas_actual_line = $(secondary_demod_canvas_container).height() - 1;
    secondary_demod_current_canvas_index = 0;
    secondary_demod_canvases_initialized = true;
    mkscale(); //so that the secondary waterfall zoom level will be initialized
}

function secondary_demod_canvases_update_top() {
    for (var i = 0; i < 2; i++) {
        secondary_demod_canvases[i].style.transform = 'translate(0, ' + secondary_demod_canvases[i].openwebrx_top + 'px)';
    }
}

function secondary_demod_swap_canvases() {
    secondary_demod_canvases[0 + !secondary_demod_current_canvas_index].openwebrx_top -= $(secondary_demod_canvas_container).height() * 2;
    secondary_demod_current_canvas_index = 0 + !secondary_demod_current_canvas_index;
    secondary_demod_current_canvas_context = secondary_demod_canvases[secondary_demod_current_canvas_index].getContext("2d");
    secondary_demod_current_canvas_actual_line = $(secondary_demod_canvas_container).height() - 1;
}

function secondary_demod_init() {
    secondary_demod_canvas_container = $("#openwebrx-digimode-canvas-container")[0];
    $(secondary_demod_canvas_container)
        .mousemove(secondary_demod_canvas_container_mousemove)
        .mouseup(secondary_demod_canvas_container_mouseup)
        .mousedown(secondary_demod_canvas_container_mousedown)
        .mouseenter(secondary_demod_canvas_container_mousein)
        .mouseleave(secondary_demod_canvas_container_mouseleave);
    $('#openwebrx-panel-wsjt-message').wsjtMessagePanel();
    $('#openwebrx-panel-packet-message').packetMessagePanel();
    $('#openwebrx-panel-pocsag-message').pocsagMessagePanel();
    $('#openwebrx-panel-5tone-message').fiveToneMessagePanel();
    $('#openwebrx-panel-2tone-message').twoToneMessagePanel();
    $('#openwebrx-panel-js8-message').js8();
}

function secondary_demod_push_data(x) {
    x = Array.from(x).filter(function (y) {
        var c = y.charCodeAt(0);
        return (c === 10 || (c >= 32 && c <= 126));
    }).map(function (y) {
        if (y === "&")
            return "&amp;";
        if (y === "<") return "&lt;";
        if (y === ">") return "&gt;";
        if (y === " ") return "&nbsp;";
        if (y === "\n") return "<br />";
        return y;
    }).join("");
    $("#openwebrx-cursor-blink").before(x);
}

function secondary_demod_waterfall_add(data) {
    var w = secondary_fft_size;

    //Add line to waterfall image
    var oneline_image = secondary_demod_current_canvas_context.createImageData(w, 1);
    for (var x = 0; x < w; x++) {
        var color = waterfall_mkcolor(data[x] + secondary_demod_fft_offset_db);
        for (var i = 0; i < 3; i++) oneline_image.data[x * 4 + i] = color[i];
        oneline_image.data[x * 4 + 3] = 255;
    }

    //Draw image
    secondary_demod_current_canvas_context.putImageData(oneline_image, 0, secondary_demod_current_canvas_actual_line--);
    secondary_demod_canvases.map(function (x) {
        x.openwebrx_top += 1;
    })
    ;
    secondary_demod_canvases_update_top();
    if (secondary_demod_current_canvas_actual_line < 0) secondary_demod_swap_canvases();
}

function secondary_demod_update_marker() {
    var width = Math.max((secondary_bw / if_samp_rate) * secondary_demod_canvas_width, 5);
    var center_at = ((secondary_demod_channel_freq - secondary_demod_low_cut) / if_samp_rate) * secondary_demod_canvas_width;
    var left = center_at - width / 2;
    $("#openwebrx-digimode-select-channel").width(width).css("left", left + "px")
}

function secondary_demod_update_channel_freq_from_event(evt) {
    if (typeof evt !== "undefined") {
        var relativeX = (evt.offsetX) ? evt.offsetX : evt.layerX;
        secondary_demod_channel_freq = secondary_demod_low_cut +
            (relativeX / $(secondary_demod_canvas_container).width()) * (secondary_demod_high_cut - secondary_demod_low_cut);
    }
    if (!secondary_demod_waiting_for_set) {
        secondary_demod_waiting_for_set = true;
        window.setTimeout(function () {
                $('#openwebrx-panel-receiver').demodulatorPanel().getDemodulator().set_secondary_offset_freq(Math.floor(secondary_demod_channel_freq));
                secondary_demod_waiting_for_set = false;
            },
            50
        )
        ;
    }
    secondary_demod_update_marker();
}

function secondary_demod_canvas_container_mousein() {
    $("#openwebrx-digimode-select-channel").css("opacity", "0.7"); //.css("border-width", "1px");
}

function secondary_demod_canvas_container_mouseleave() {
    $("#openwebrx-digimode-select-channel").css("opacity", "0");
}

function secondary_demod_canvas_container_mousemove(evt) {
    if (secondary_demod_mousedown) secondary_demod_update_channel_freq_from_event(evt);
}

function secondary_demod_canvas_container_mousedown(evt) {
    if (evt.which === 1) secondary_demod_mousedown = true;
}

function secondary_demod_canvas_container_mouseup(evt) {
    if (evt.which === 1) secondary_demod_mousedown = false;
    secondary_demod_update_channel_freq_from_event(evt);
}


function secondary_demod_waterfall_set_zoom(low_cut, high_cut) {
    if (!secondary_demod_canvases_initialized) return;
    secondary_demod_low_cut = low_cut;
    secondary_demod_high_cut = high_cut;
    var shown_bw = high_cut - low_cut;
    secondary_demod_canvas_width = $(secondary_demod_canvas_container).width() * (if_samp_rate) / shown_bw;
    secondary_demod_canvas_left = (-secondary_demod_canvas_width / 2) - (low_cut / if_samp_rate) * secondary_demod_canvas_width;
    secondary_demod_canvases.map(function (x) {
        $(x).css({
            left: secondary_demod_canvas_left + "px",
            width: secondary_demod_canvas_width + "px"
        });
    });
    secondary_demod_update_channel_freq_from_event();
}

function sdr_profile_changed() {
    var value = $('#openwebrx-sdr-profiles-listbox').val();
    ws.send(JSON.stringify({type: "selectprofile", params: {profile: value}}));
}

function toggle_memory_panel() {
    var panel = $('#openwebrx-panel-memory');
    if (panel.is(':visible')) {
        panel.hide();
    } else {
        panel.show();
        // loads whichever source the selector is on
        switch_memory_source();
        update_5tone_option();
    }
}

function close_memory_panel() {
    $('#openwebrx-panel-memory').hide();
    cancel_edit_memory();
}

function load_memories() {
    ws.send(JSON.stringify({type: "getmemories"}));
}

var memory_editing = null;

function edit_memory(name) {
    var m = memory_cache.filter(function(x) { return x.name === name; })[0];
    if (!m) return;
    memory_editing = name;
    $('#memory-name').val(m.name);
    $('#memory-freq').val(format_memory_freq(m.frequency));
    var cinque = (m.modulation === '5tone');
    $('#memory-mod').val(cinque ? 'nfm' : (m.modulation || 'nfm'));
    update_5tone_option();
    $('#memory-5tone').prop('checked', cinque);
    $('#memory-edit-name').text(name);
    $('#memory-edit-banner').show();
    $('#memory-save-button').text('Update');
    $('#memory-name').focus();
}

function cancel_edit_memory() {
    memory_editing = null;
    $('#memory-edit-banner').hide();
    $('#memory-save-button').text('Save');
    $('#memory-name').val('');
    $('#memory-freq').val('');
    $('#memory-5tone').prop('checked', false);
}

function update_5tone_option() {
    // 5 tone rides on narrow FM, so the option only makes sense there; the
    // stored modulation becomes "5tone", which OpenWebRX resolves to nfm plus
    // the secondary decoder
    var mod = $('#memory-mod').val();
    var adatto = (mod === 'nfm' || mod === 'fm');
    $('#memory-5tone-row').toggle(adatto);
    if (!adatto) $('#memory-5tone').prop('checked', false);
}

function save_memory_from_panel() {
    if (is_bandplan()) return save_bandplan_from_panel();
    var name = $('#memory-name').val().trim();
    var freq_mhz = parseFloat($('#memory-freq').val());
    var modulation = $('#memory-mod').val();
    if ($('#memory-5tone').is(':checked') && (modulation === 'nfm' || modulation === 'fm')) {
        modulation = '5tone';
    }

    if (!name || !freq_mhz || freq_mhz <= 0) {
        divlog('Please enter a valid name and frequency');
        return;
    }

    var freq_hz = Math.round(freq_mhz * 1000000);
    ws.send(JSON.stringify({
        type: "savememory",
        params: {
            name: name,
            frequency: freq_hz,
            modulation: modulation
        }
    }));

    // The backend replaces by name: when renaming during an edit the old entry
    // would stay behind as a duplicate. It is removed AFTER the save, so there is
    // never a moment where the bookmark does not exist.
    if (memory_editing && memory_editing !== name) {
        ws.send(JSON.stringify({
            type: "deletememory",
            params: { name: memory_editing }
        }));
    }

    cancel_edit_memory();
}

function save_bandplan_from_panel() {
    var mode = $('#memory-name').val().trim();
    var freq_mhz = parseFloat($('#memory-freq').val());
    if (!mode || !freq_mhz || freq_mhz <= 0) {
        divlog('Please enter a mode and a valid frequency', true);
        return;
    }
    var params = {modulation: mode, frequency: Math.round(freq_mhz * 1000000)};
    // the server removes the original entry before inserting the new one, so
    // changing mode or frequency moves it instead of leaving a duplicate
    if (memory_editing && typeof memory_editing === 'object') params.original = memory_editing;
    ws.send(JSON.stringify({type: 'savebandplanentry', params: params}));
    cancel_edit_memory();
}

function recall_memory(name) {
    var m = memory_cache.filter(function(x) { return x.name === name; })[0];
    if (m) recall_entry(m);
}

function recall_entry(m) {
    if (!m) return;

    // Same as clicking a native bookmark: move the demodulator, not the SDR
    // centre. Moving the centre while leaving the offset untouched tuned to
    // bookmark + previous offset, that is the wrong frequency, and on top of that
    // it moved the band for every connected client.
    var panel = $('#openwebrx-panel-receiver').demodulatorPanel();
    var offset = m.frequency - center_freq;

    if (Math.abs(offset) < (bandwidth / 2) * 0.95) {
        panel.getDemodulator().set_offset_frequency(offset);
        if (m.modulation) panel.setMode(m.modulation);
        divlog('Bookmark: ' + m.name + ' -> ' + format_memory_freq(m.frequency) + ' MHz');
    } else {
        // outside the visible band: the centre has to move, and only then does
        // the offset go back to zero, because the bookmark ends up at the centre
        ws.send(JSON.stringify({ type: 'setcenterfreq', params: { freq: m.frequency } }));
        setTimeout(function() {
            var p = $('#openwebrx-panel-receiver').demodulatorPanel();
            p.getDemodulator().set_offset_frequency(0);
            if (m.modulation) p.setMode(m.modulation);
        }, 900);
        divlog('Bookmark out of band: ' + m.name + ' -> ' + format_memory_freq(m.frequency) + ' MHz (moving the centre)');
    }

    close_memory_panel();
}

function delete_memory(name) {
    if (confirm('Delete the bookmark "' + name + '"?')) {
        ws.send(JSON.stringify({
            type: "deletememory",
            params: { name: name }
        }));
    }
}

// One place decides how a frequency is written out, so the centre frequency box
// and the rest of the interface cannot disagree about the same number.
//
// Three decimals of a megahertz is kilohertz resolution, and VHF is on a
// 12.5 kHz raster: 145.0125 MHz comes out 145.013, which is not a channel. That
// is not only cosmetic - the step buttons read the box back, so one rewrite put
// every later step 500 Hz off a frequency nobody had tuned.
//
// Letting the number print itself gives the shortest text that reads back as
// the same frequency, so 145.0125 survives and so does a 6.25 kHz raster. The
// padding is only there to keep the familiar 145.700 for the round ones.
function format_freq_value(hz, unit) {
    unit = unit || 1000000;
    var value = hz / unit;
    var out = String(value);
    if (unit >= 1000000) {
        var decimals = (out.split('.')[1] || '').length;
        if (decimals < 3) out = value.toFixed(3);
    }
    return out;
}

function format_memory_freq(hz) {
    return format_freq_value(hz, 1000000);
}

var memory_cache = [];
var bandplan_cache = [];

function is_bandplan() {
    return ($('#memory-source').val() || 'bookmarks') === 'bandplan';
}

function switch_memory_source() {
    cancel_edit_memory();
    var bandplan = is_bandplan();
    $('#memory-title').text(bandplan ? 'Bandplan' : 'Bookmarks');
    // in the bandplan the label IS the mode, and the modes go well beyond the
    // handful in the dropdown (ft8, wspr, packet, q65...), so the name field
    // doubles as a free text mode field and the dropdown is hidden
    $('#memory-name').attr('placeholder', bandplan ? 'Mode (ft8, packet, ...)' : 'Bookmark name');
    $('#memory-mod').closest('div').toggle(!bandplan);
    if (bandplan) {
        ws.send(JSON.stringify({type: 'getbandplan'}));
    } else {
        load_memories();
    }
    render_memories();
}

function on_bandplan_received(entries) {
    bandplan_cache = entries;
    render_memories();
}

function on_bandplan_result(result) {
    divlog(result.message, !result.ok);
}

function tune_entry(m) {
    if (is_bandplan()) {
        // same path as a bookmark, the entry just carries the mode as its name
        recall_entry({name: m.name, frequency: m.frequency, modulation: m.modulation});
    } else {
        recall_memory(m.name);
    }
}

function edit_entry(m) {
    if (!is_bandplan()) return edit_memory(m.name);
    memory_editing = {band: m.band, modulation: m.modulation, frequency: m.frequency};
    $('#memory-name').val(m.modulation);
    $('#memory-freq').val(format_memory_freq(m.frequency));
    $('#memory-edit-name').text(m.modulation + ' @ ' + format_memory_freq(m.frequency) + ' MHz');
    $('#memory-edit-banner').show();
    $('#memory-save-button').text('Update');
    $('#memory-name').focus();
}

function delete_entry(m) {
    if (!is_bandplan()) return delete_memory(m.name);
    if (!confirm('Delete "' + m.modulation + '" at ' + format_memory_freq(m.frequency) + ' MHz?')) return;
    ws.send(JSON.stringify({
        type: 'deletebandplanentry',
        params: {band: m.band, modulation: m.modulation, frequency: m.frequency}
    }));
}


function on_memories_received(memories) {
    memory_cache = memories;
    render_memories();
}

function render_memories() {
    var list = $('#memory-list');
    var filter = ($('#memory-search').val() || '').trim().toLowerCase();
    var bandplan = is_bandplan();
    var cache = bandplan ? bandplan_cache : memory_cache;

    var entries = cache;
    if (filter) {
        entries = cache.filter(function(m) {
            return (m.name || '').toLowerCase().indexOf(filter) > -1
                || format_memory_freq(m.frequency).indexOf(filter) > -1
                || (m.modulation || '').toLowerCase().indexOf(filter) > -1
                || (m.band || '').toLowerCase().indexOf(filter) > -1;
        });
    }

    var order = $('#memory-sort').val() || 'name';
    entries = entries.slice().sort(function(a, b) {
        if (order === 'freq') return a.frequency - b.frequency;
        // many bookmarks are named "-": on equal names sort by frequency
        var n = (a.name || '').localeCompare(b.name || '', 'it', { sensitivity: 'base', numeric: true });
        return n !== 0 ? n : a.frequency - b.frequency;
    });

    $('#memory-count').text(filter ? entries.length + ' of ' + cache.length : String(cache.length));

    list.html('');

    if (entries.length === 0) {
        var vuoto = bandplan
            ? (filter ? 'No matching entry' : 'No bandplan entries')
            : (filter ? 'No matching bookmark' : 'No bookmarks stored');
        list.html('<div style="font-size: 11px; color: #888;">' + vuoto + '</div>');
        return;
    }

    entries.forEach(function(m) {
        var freq_mhz = format_memory_freq(m.frequency);

        var $row = $('<div></div>').css({
            padding: '4px', borderBottom: '1px solid #444',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center'
        });

        var $info = $('<div></div>').css('font-size', '11px');
        $info.append($('<strong></strong>').css('color', bandplan ? '#8f8' : '#0ff').text(m.name));
        $info.append('<br>');
        var sub = freq_mhz + ' MHz' + (bandplan && m.band ? '  \u00b7  ' + m.band : '');
        $info.append($('<span></span>').css('color', '#aaa').text(sub));

        var $recall = $('<button></button>')
            .css({ fontSize: '10px', padding: '2px 6px' })
            .text('Tune')
            .on('click', function() { tune_entry(m); });

        var $edit = $('<button></button>')
            .css({ fontSize: '10px', padding: '2px 6px' })
            .attr('title', 'Edit')
            .text('Edit')
            .on('click', function() { edit_entry(m); });

        var $del = $('<button></button>')
            .css({ fontSize: '10px', padding: '2px 6px', color: '#f55' })
            .attr('title', 'Delete')
            .html('&times;')
            .on('click', function() { delete_entry(m); });

        var $actions = $('<div></div>')
            .css({ display: 'flex', gap: '3px' })
            .append($recall, $edit, $del);

        list.append($row.append($info, $actions));
    });
}

function on_memory_saved(memory) {
    divlog('Bookmark saved: ' + memory.name + ' -> ' + format_memory_freq(memory.frequency) + ' MHz');
    load_memories();
}

function on_memory_deleted(name) {
    divlog('Bookmark deleted: ' + name);
    load_memories();
}

function update_freq_step() {
    var unit = parseInt($('#openwebrx-freq-unit').val());
    var $input = $('#openwebrx-frequency-input');
    if (unit >= 1000000000) { $input.attr('step', '0.025'); $input.attr('min', '0.0005'); $input.attr('max', '1.766'); }
    else if (unit >= 1000000) { $input.attr('step', '0.025'); $input.attr('min', '0.5'); $input.attr('max', '1766'); }
    else if (unit >= 1000) { $input.attr('step', '25'); $input.attr('min', '500'); $input.attr('max', '1766000'); }
    else { $input.attr('step', '25000'); $input.attr('min', '500000'); $input.attr('max', '1766000000'); }
}

function set_frequency() {
    var freq = parseFloat($('#openwebrx-frequency-input').val());
    var unit = parseInt($('#openwebrx-freq-unit').val());
    if (freq && freq > 0) {
        var freq_hz = Math.round(freq * unit);
        ws.send(JSON.stringify({type: 'setcenterfreq', params: {freq: freq_hz}}));
        divlog('Center frequency set: ' + freq_hz + ' Hz');
    }
}

function set_samplerate() {
    var sr = parseInt($('#openwebrx-samplerate-select').val());
    ws.send(JSON.stringify({type: 'setsamplerate', params: {samp_rate: sr}}));
    divlog('Sample rate set: ' + sr + ' Hz');
}


function save_defaults() {
    // Only the two values the receiver panel still owns. Gain and squelch are
    // set from the settings pages, so saving them from here would fight with
    // that and overwrite deliberate choices.
    var params = {};

    var freq = parseFloat($('#openwebrx-frequency-input').val());
    var unit = parseInt($('#openwebrx-freq-unit').val());
    if (freq && unit) params.center_freq = Math.round(freq * unit);

    var sr = parseInt($('#openwebrx-samplerate-select').val());
    if (sr) params.samp_rate = sr;

    ws.send(JSON.stringify({type: 'savedefaults', params: params}));
}

function step_center_freq(delta_hz) {
    // moves the centre frequency and applies it straight away
    var unit = parseInt($('#openwebrx-freq-unit').val()) || 1000000;
    var current = parseFloat($('#openwebrx-frequency-input').val());
    if (isNaN(current)) current = center_freq / unit;

    var nuova_hz = Math.round(current * unit) + delta_hz;
    if (nuova_hz < 500000) {
        divlog('Frequency out of range', true);
        return;
    }
    $('#openwebrx-frequency-input').val(nuova_hz / unit);
    set_frequency();
}

function on_defaults_saved(result) {
    divlog(result.message, !result.ok);
}

