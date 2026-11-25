/*
 * The receiver location picker.
 *
 * Upstream builds this on locationPicker, a thin wrapper around the Google
 * Maps API, so picking the receiver's position needed a billing-enabled API
 * key. It is drawn with Leaflet on the same tiles as the main map instead.
 */
$.fn.mapInput = function() {
    var DEFAULT_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
    var DEFAULT_TILE_ATTRIBUTION =
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

    this.each(function() {
        var $el = $(this);
        var field_id = $el.attr("for");
        var $lat = $('#' + field_id + '-lat');
        var $lon = $('#' + field_id + '-lon');

        var lat = parseFloat($lat.val());
        var lon = parseFloat($lon.val());
        if (isNaN(lat)) lat = 0;
        if (isNaN(lon)) lon = 0;

        $el.css('height', '200px');

        var map = L.map($el.get(0)).setView([lat, lon], 7);
        L.tileLayer($el.data('tile-url') || DEFAULT_TILE_URL, {
            maxZoom: 19,
            attribution: $el.data('tile-attribution') || DEFAULT_TILE_ATTRIBUTION
        }).addTo(map);

        var marker = L.marker([lat, lon], {draggable: true}).addTo(map);

        var store = function(latlng) {
            // six decimals is about ten centimetres, far beyond what a
            // receiver location needs, and keeps the field readable
            $lat.val(latlng.lat.toFixed(6));
            $lon.val(latlng.lng.toFixed(6));
        };

        marker.on('dragend', function() {
            store(marker.getLatLng());
        });
        map.on('click', function(e) {
            marker.setLatLng(e.latlng);
            store(e.latlng);
        });

        // typing into the fields should move the marker, so the two ways of
        // setting the position cannot drift apart
        var fromFields = function() {
            var la = parseFloat($lat.val());
            var lo = parseFloat($lon.val());
            if (isNaN(la) || isNaN(lo)) return;
            marker.setLatLng([la, lo]);
            map.panTo([la, lo]);
        };
        $lat.on('change', fromFields);
        $lon.on('change', fromFields);

        // the container is laid out by bootstrap after this runs, and a map
        // sized before its container is left showing a grey band
        setTimeout(function() { map.invalidateSize(); }, 0);
    });
};
