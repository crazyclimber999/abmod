/*
 * Map view.
 *
 * Upstream OpenWebRX draws this map with the Google Maps JavaScript API, which
 * needs an API key tied to a billing account: without one the map stays blank,
 * and the key is visible to every visitor because the browser loads the API
 * with it. This version draws the same map with Leaflet on OpenStreetMap
 * tiles, so the receiver works out of the box and no key has to be handed out.
 *
 * The tile source is configurable, so a different provider can be used without
 * touching this file.
 */

$(function(){
    var query = window.location.search.replace(/^\?/, '').split('&').map(function(v){
        var s = v.split('=');
        var r = {};
        r[s[0]] = s.slice(1).join('=');
        return r;
    }).reduce(function(a, b){
        return a.assign(b);
    });

    var expectedCallsign;
    if (query.callsign) expectedCallsign = decodeURIComponent(query.callsign);
    var expectedLocator;
    if (query.locator) expectedLocator = query.locator;

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

    var map;
    var markers = {};
    var rectangles = {};
    var receiverMarker;
    var updateQueue = [];

    // reasonable default; will be overriden by server
    var retention_time = 2 * 60 * 60 * 1000;
    var strokeOpacity = 0.8;
    var fillOpacity = 0.35;

    var DEFAULT_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
    var DEFAULT_TILE_ATTRIBUTION =
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

    var colorKeys = {};
    var colorScale = chroma.scale(['red', 'blue', 'green']).mode('hsl');
    var getColor = function(id){
        if (!id) return "#000000";
        if (!colorKeys[id]) {
            var keys = Object.keys(colorKeys);
            keys.push(id);
            keys.sort(function(a, b) {
                var pa = parseFloat(a);
                var pb = parseFloat(b);
                if (isNaN(pa) || isNaN(pb)) return a.localeCompare(b);
                return pa - pb;
            });
            var colors = colorScale.colors(keys.length);
            colorKeys = {};
            keys.forEach(function(key, index) {
                colorKeys[key] = colors[index];
            });
            reColor();
            updateLegend();
        }
        return colorKeys[id];
    }

    // when the color palette changes, update all grid squares with new color
    var reColor = function() {
        $.each(rectangles, function(_, r) {
            var color = getColor(colorAccessor(r));
            r.setStyle({
                color: color,
                fillColor: color
            });
        });
    }

    var colorMode = 'byband';
    var colorAccessor = function(r) {
        switch (colorMode) {
            case 'byband':
                return r.band;
            case 'bymode':
                return r.mode;
        }
    };

    $(function(){
        $('#openwebrx-map-colormode').on('change', function(){
            colorMode = $(this).val();
            colorKeys = {};
            filterRectangles(allRectangles);
            reColor();
            updateLegend();
        });
    });

    var updateLegend = function() {
        var lis = $.map(colorKeys, function(value, key) {
            // fake rectangle to test if the filter would match
            var fakeRectangle = Object.fromEntries([[colorMode.slice(2), key]]);
            var disabled = rectangleFilter(fakeRectangle) ? '' : ' disabled';
            return '<li class="square' + disabled + '" data-selector="' + key + '"><span class="illustration" style="background-color:' + chroma(value).alpha(fillOpacity) + ';border-color:' + chroma(value).alpha(strokeOpacity) + ';"></span>' + key + '</li>';
        });
        $(".openwebrx-map-legend .content").html('<ul>' + lis.join('') + '</ul>');
    }

    /*
     * APRS symbols are a sprite sheet: the symbol is a window onto one image,
     * and a marker whose course is known is rotated to point that way. Google's
     * version of this was a custom OverlayView that positioned a div by hand;
     * Leaflet has divIcon for exactly this, so the marker is just an icon and
     * Leaflet keeps it in place as the map moves.
     */
    var aprsIcon = function(symbol, course) {
        var tableId = symbol.table === '/' ? 0 : 1;
        var sprite = function(index, file) {
            return 'background-image:url(aprs-symbols/aprs-symbols-24-' + file + '@2x.png);'
                + 'background-size:384px 144px;'
                + 'background-position:' + (-(index % 16) * 24) + 'px ' + (-Math.floor(index / 16) * 24) + 'px;';
        };

        var style = 'width:24px;height:24px;' + sprite(symbol.index, tableId);
        if (course) {
            style += course > 180
                ? 'transform:scalex(-1) rotate(' + (270 - course) + 'deg);'
                : 'transform:rotate(' + (course - 90) + 'deg);';
        }

        var inner = '';
        // an overlaid character from a third table, used by symbols that are
        // not in the two standard tables
        if (symbol.table !== '/' && symbol.table !== '\\') {
            inner = '<div style="width:24px;height:24px;' + sprite(symbol.tableindex, 2) + '"></div>';
        }

        return L.divIcon({
            html: '<div style="' + style + '">' + inner + '</div>',
            className: 'aprs-marker',
            iconSize: [24, 24],
            iconAnchor: [12, 12],
            popupAnchor: [0, -12]
        });
    };

    var locatorToBounds = function(locator) {
        var lat = (locator.charCodeAt(1) - 65 - 9) * 10 + Number(locator[3]);
        var lon = (locator.charCodeAt(0) - 65 - 9) * 20 + Number(locator[2]) * 2;
        return {
            bounds: L.latLngBounds([lat, lon], [lat + 1, lon + 2]),
            center: L.latLng(lat + .5, lon + 1)
        };
    };

    var processUpdates = function(updates) {
        if (!map) {
            updateQueue = updateQueue.concat(updates);
            return;
        }
        updates.forEach(function(update){

            switch (update.location.type) {
                case 'latlon':
                    var pos = L.latLng(update.location.lat, update.location.lon);
                    var isAprs = !!update.location.symbol;
                    var marker = markers[update.callsign];

                    // a station that starts sending a symbol needs a different
                    // kind of marker, so the old one is thrown away
                    if (marker && marker.isAprs !== isAprs) {
                        map.removeLayer(marker);
                        marker = null;
                    }

                    if (!marker) {
                        marker = isAprs
                            ? L.marker(pos, {icon: aprsIcon(update.location.symbol, update.location.course), title: update.callsign})
                            : L.marker(pos, {title: update.callsign});
                        marker.isAprs = isAprs;
                        marker.callsign = update.callsign;
                        marker.on('click', function(){
                            showMarkerInfoWindow(this.callsign, this.getLatLng());
                        });
                        marker.addTo(map);
                        markers[update.callsign] = marker;
                    } else {
                        marker.setLatLng(pos);
                        if (isAprs) {
                            marker.setIcon(aprsIcon(update.location.symbol, update.location.course));
                        }
                    }

                    marker.setOpacity(getScale(update.lastseen));
                    marker.lastseen = update.lastseen;
                    marker.mode = update.mode;
                    marker.band = update.band;
                    marker.comment = update.location.comment;

                    if (expectedCallsign && expectedCallsign == update.callsign) {
                        map.panTo(pos);
                        showMarkerInfoWindow(update.callsign, pos);
                        expectedCallsign = false;
                    }

                    if (infowindow && infowindow.callsign && infowindow.callsign == update.callsign) {
                        showMarkerInfoWindow(infowindow.callsign, pos);
                    }
                break;
                case 'locator':
                    var square = locatorToBounds(update.location.locator);
                    var rectangle = rectangles[update.callsign];
                    // the accessor is designed to work on the rectangle... but it should work on the update object, too
                    var color = getColor(colorAccessor(update));

                    if (!rectangle) {
                        rectangle = L.rectangle(square.bounds, {weight: 2});
                        rectangle.on('click', function(){
                            showLocatorInfoWindow(this.locator, this.center);
                        });
                        rectangles[update.callsign] = rectangle;
                    } else {
                        rectangle.setBounds(square.bounds);
                    }

                    rectangle.lastseen = update.lastseen;
                    rectangle.locator = update.location.locator;
                    rectangle.mode = update.mode;
                    rectangle.band = update.band;
                    rectangle.center = square.center;

                    rectangle.setStyle($.extend({
                        color: color,
                        weight: 2,
                        fillColor: color
                    }, getRectangleOpacityOptions(update.lastseen)));

                    setRectangleVisible(rectangle, rectangleFilter(rectangle));

                    if (expectedLocator && expectedLocator == update.location.locator) {
                        map.panTo(square.center);
                        showLocatorInfoWindow(expectedLocator, square.center);
                        expectedLocator = false;
                    }

                    if (infowindow && infowindow.locator && infowindow.locator == update.location.locator) {
                        showLocatorInfoWindow(infowindow.locator, square.center);
                    }
                break;
            }
        });
    };

    var setRectangleVisible = function(rectangle, visible) {
        if (visible) {
            if (!map.hasLayer(rectangle)) rectangle.addTo(map);
        } else if (map.hasLayer(rectangle)) {
            map.removeLayer(rectangle);
        }
    };

    var clearMap = function(){
        var reset = function(callsign, item) {
            if (map && map.hasLayer(item)) map.removeLayer(item);
        };
        $.each(markers, reset);
        $.each(rectangles, reset);
        if (receiverMarker && map && map.hasLayer(receiverMarker)) map.removeLayer(receiverMarker);
        markers = {};
        rectangles = {};
    };

    /*
     * Day/night terminator.
     *
     * Upstream pulls in nite-overlay.js, which is written against the Google
     * Maps API. The shape is just the line where the sun sits on the horizon,
     * so it is computed here and drawn as an ordinary polygon.
     */
    var terminator;
    var RAD = Math.PI / 180, DEG = 180 / Math.PI;

    var julianDay = function(date) {
        return date.getTime() / 86400000 + 2440587.5;
    };

    var sunPosition = function(date) {
        var jd = julianDay(date);
        var n = jd - 2451545.0;

        // mean longitude and mean anomaly of the sun
        var meanLongitude = (280.460 + 0.9856474 * n) % 360;
        var meanAnomaly = ((357.528 + 0.9856003 * n) % 360) * RAD;
        // ecliptic longitude, corrected for the orbit not being a circle
        var lambda = meanLongitude + 1.915 * Math.sin(meanAnomaly) + 0.020 * Math.sin(2 * meanAnomaly);

        var obliquity = 23.439 - 0.0000004 * n;

        var alpha = Math.atan2(
            Math.cos(obliquity * RAD) * Math.sin(lambda * RAD),
            Math.cos(lambda * RAD)
        ) * DEG;
        var delta = Math.asin(Math.sin(obliquity * RAD) * Math.sin(lambda * RAD)) * DEG;

        // Greenwich mean sidereal time, in degrees
        var gmst = (18.697374558 + 24.06570982441908 * n) % 24;
        if (gmst < 0) gmst += 24;

        return {alpha: alpha, delta: delta, gmst: gmst * 15};
    };

    var terminatorLatLngs = function(date) {
        var sun = sunPosition(date);
        var points = [];
        for (var lon = -180; lon <= 180; lon += 1) {
            var hourAngle = sun.gmst + lon - sun.alpha;
            var lat = Math.atan(-Math.cos(hourAngle * RAD) / Math.tan(sun.delta * RAD)) * DEG;
            points.push([lat, lon]);
        }
        // close the shape over whichever pole is in darkness
        var pole = sun.delta > 0 ? -90 : 90;
        points.push([pole, 180]);
        points.push([pole, -180]);
        return points;
    };

    var refreshTerminator = function() {
        if (!map) return;
        var points = terminatorLatLngs(new Date());
        if (terminator) {
            terminator.setLatLngs(points);
        } else {
            terminator = L.polygon(points, {
                stroke: false,
                fillColor: '#000',
                fillOpacity: 0.2,
                interactive: false
            }).addTo(map);
        }
    };

    var createMap = function(receiverPos, config) {
        map = L.map($('.openwebrx-map')[0], {
            center: [receiverPos.lat, receiverPos.lng],
            zoom: 5,
            worldCopyJump: true
        });

        L.tileLayer(config.map_tile_url || DEFAULT_TILE_URL, {
            maxZoom: 19,
            attribution: config.map_tile_attribution || DEFAULT_TILE_ATTRIBUTION
        }).addTo(map);

        refreshTerminator();
        setInterval(refreshTerminator, 10000);

        var $legend = $(".openwebrx-map-legend");
        setupLegendFilters($legend);
        var LegendControl = L.Control.extend({
            options: {position: 'bottomleft'},
            onAdd: function() {
                var el = $legend[0];
                el.style.display = 'block';
                // map.css hides the legend until something takes charge of it
                el.classList.add('leaflet-control');
                // without this, dragging or scrolling over the legend moves
                // the map underneath it
                L.DomEvent.disableClickPropagation(el);
                L.DomEvent.disableScrollPropagation(el);
                return el;
            }
        });
        map.addControl(new LegendControl());

        map.on('popupclose', function(e) {
            if (e.popup === infowindow) {
                delete infowindow.locator;
                delete infowindow.callsign;
            }
        });

        processUpdates(updateQueue);
        updateQueue = [];
    };

    var reconnect_timeout = false;

    var config = {}

    var connect = function(){
        var ws = new WebSocket(ws_url);
        ws.onopen = function(){
            ws.send("SERVER DE CLIENT client=map.js type=map");
            reconnect_timeout = false
        };

        ws.onmessage = function(e){
            if (typeof e.data != 'string') {
                console.error("unsupported binary data on websocket; ignoring");
                return
            }
            if (e.data.substr(0, 16) == "CLIENT DE SERVER") {
                return
            }
            try {
                var json = JSON.parse(e.data);
                switch (json.type) {
                    case "config":
                        Object.assign(config, json.value);
                        if ('receiver_gps' in config) {
                            var receiverPos = {
                                lat: config.receiver_gps.lat,
                                lng: config.receiver_gps.lon
                            };
                            if (!map) {
                                createMap(receiverPos, config);
                            }
                            if (!receiverMarker) {
                                receiverMarker = L.marker([receiverPos.lat, receiverPos.lng], {
                                    title: config['receiver_name']
                                });
                                receiverMarker.on('click', function() {
                                    showReceiverInfoWindow(receiverMarker);
                                });
                                receiverMarker.addTo(map);
                            } else {
                                receiverMarker.setLatLng([receiverPos.lat, receiverPos.lng]);
                            }
                            receiverMarker.config = config;
                        }
                        if ('receiver_name' in config && receiverMarker) {
                            receiverMarker.options.title = config['receiver_name'];
                        }
                        if ('map_position_retention_time' in config) {
                            retention_time = config.map_position_retention_time * 1000;
                        }
                    break;
                    case "update":
                        processUpdates(json.value);
                    break;
                    case 'receiver_details':
                        $('.webrx-top-container').header().setDetails(json['value']);
                    break;
                    default:
                        console.warn('received message of unknown type: ' + json['type']);
                }
            } catch (e) {
                // don't lose exception
                console.error(e);
            }
        };
        ws.onclose = function(){
            clearMap();
            if (reconnect_timeout) {
                // max value: roundabout 8 and a half minutes
                reconnect_timeout = Math.min(reconnect_timeout * 2, 512000);
            } else {
                // initial value: 1s
                reconnect_timeout = 1000;
            }
            setTimeout(connect, reconnect_timeout);
        };

        window.onbeforeunload = function() { //http://stackoverflow.com/questions/4812686/closing-websocket-correctly-html5-javascript
            ws.onclose = function () {};
            ws.close();
        };
    };

    connect();

    var infowindow;
    var getInfoWindow = function() {
        if (!infowindow) {
            infowindow = L.popup();
        }
        delete infowindow.locator;
        delete infowindow.callsign;
        return infowindow;
    }

    var showLocatorInfoWindow = function(locator, pos) {
        var infowindow = getInfoWindow();
        infowindow.locator = locator;
        var inLocator = $.map(rectangles, function(r, callsign) {
            return {callsign: callsign, locator: r.locator, lastseen: r.lastseen, mode: r.mode, band: r.band}
        }).filter(rectangleFilter).filter(function(d) {
            return d.locator == locator;
        }).sort(function(a, b){
            return b.lastseen - a.lastseen;
        });
        infowindow.setContent(
            '<h3>Locator: ' + locator + '</h3>' +
            '<div>Active Callsigns:</div>' +
            '<ul>' +
                inLocator.map(function(i){
                    var timestring = moment(i.lastseen).fromNow();
                    var message = i.callsign + ' (' + timestring + ' using ' + i.mode;
                    if (i.band) message += ' on ' + i.band;
                    message += ')';
                    return '<li>' + message + '</li>'
                }).join("") +
            '</ul>'
        );
        infowindow.setLatLng(pos);
        infowindow.openOn(map);
    };

    var showMarkerInfoWindow = function(callsign, pos) {
        var infowindow = getInfoWindow();
        infowindow.callsign = callsign;
        var marker = markers[callsign];
        var timestring = moment(marker.lastseen).fromNow();
        var commentString = "";
        if (marker.comment) {
            commentString = '<div>' + marker.comment + '</div>';
        }
        infowindow.setContent(
            '<h3>' + callsign + '</h3>' +
            '<div>' + timestring + ' using ' + marker.mode + ( marker.band ? ' on ' + marker.band : '' ) + '</div>' +
            commentString
        );
        infowindow.setLatLng(pos);
        infowindow.openOn(map);
    }

    var showReceiverInfoWindow = function(marker) {
        var infowindow = getInfoWindow()
        infowindow.setContent(
            '<h3>' + marker.config['receiver_name'] + '</h3>' +
            '<div>Receiver location</div>'
        );
        infowindow.setLatLng(marker.getLatLng());
        infowindow.openOn(map);
    }

    var getScale = function(lastseen) {
        var age = new Date().getTime() - lastseen;
        var scale = 1;
        if (age >= retention_time / 2) {
            scale = (retention_time - age) / (retention_time / 2);
        }
        return Math.max(0, Math.min(1, scale));
    };

    var getRectangleOpacityOptions = function(lastseen) {
        var scale = getScale(lastseen);
        return {
            opacity: strokeOpacity * scale,
            fillOpacity: fillOpacity * scale
        };
    };

    // fade out / remove positions after time
    setInterval(function(){
        if (!map) return;
        var now = new Date().getTime();
        $.each(rectangles, function(callsign, m) {
            var age = now - m.lastseen;
            if (age > retention_time) {
                delete rectangles[callsign];
                setRectangleVisible(m, false);
                return;
            }
            m.setStyle(getRectangleOpacityOptions(m.lastseen));
        });
        $.each(markers, function(callsign, m) {
            var age = now - m.lastseen;
            if (age > retention_time) {
                delete markers[callsign];
                if (map.hasLayer(m)) map.removeLayer(m);
                return;
            }
            m.setOpacity(getScale(m.lastseen));
        });
    }, 1000);

    var rectangleFilter = allRectangles = function() { return true; };

    var filterRectangles = function(filter) {
        rectangleFilter = filter;
        $.each(rectangles, function(_, r) {
            setRectangleVisible(r, rectangleFilter(r));
        });
    };

    var setupLegendFilters = function($legend) {
        $content = $legend.find('.content');
        $content.on('click', 'li', function() {
            var $el = $(this);
            $lis = $content.find('li');
            if ($lis.hasClass('disabled') && !$el.hasClass('disabled')) {
                $lis.removeClass('disabled');
                filterRectangles(allRectangles);
            } else {
                $el.removeClass('disabled');
                $lis.filter(function() {
                    return this != $el[0]
                }).addClass('disabled');

                var key = colorMode.slice(2);
                var selector = $el.data('selector');
                filterRectangles(function(r) {
                    return r[key] === selector;
                });
            }
        });
    }

});
