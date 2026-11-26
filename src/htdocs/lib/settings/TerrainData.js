/*
 * Elevation data status and download, next to the radius that decides it.
 *
 * The radius itself is saved by "Apply and save" like any other setting; the
 * data it describes is a few hundred megabytes fetched from a public tile
 * service, which is why saving the page does not start a download. A settings
 * save that quietly pulls 250 MB over a domestic line, with no progress and no
 * way to stop it, is the kind of surprise that gets blamed on something else
 * entirely. So the status sits here, where the radius is, and the download is
 * a button you press.
 *
 * The status always describes the radius currently SAVED, not the one typed in
 * the box - the server reads the configuration, not the form - so a changed
 * radius has to be saved before the figures mean anything.
 */
$(function() {
    var $field = $('#terrain_radius_km');
    if (!$field.length) return;

    var $note = $('<small class="d-block text-muted mt-1"></small>');
    var $button = $('<button type="button" class="btn btn-sm btn-secondary mt-1">' +
                      'Check elevation data</button>');
    // The field sits inside an input-group because of its "km" suffix, so the
    // button goes after that group rather than after the input itself, where
    // it would be drawn as part of the group.
    var $group = $field.closest('.input-group');
    ($group.length ? $group : $field).after($note).after($button);

    var timer = null;
    var downloading = false;

    var say = function(text, cls) {
        $note.removeClass('text-success text-danger text-muted')
             .addClass(cls || 'text-muted').html(text);
    };

    var megabyte = function(b) {
        return Math.round(b / 1e6) + ' MB';
    };

    var ask = function(action, afterwards) {
        return $.ajax({
            url: 'bookmarkimport/terrain', type: 'POST',
            data: JSON.stringify(action ? {action: action} : {}),
            contentType: 'application/json', dataType: 'json'
        }).done(function(r) {
            show(r);
            if (afterwards) afterwards(r);
        }).fail(function(xhr) {
            var message = 'Could not check the elevation data.';
            try { message = JSON.parse(xhr.responseText).error || message; } catch (e) {}
            say(message, 'text-danger');
            stopPolling();
        });
    };

    var stopPolling = function() {
        if (timer) { clearInterval(timer); timer = null; }
        downloading = false;
        $button.prop('disabled', false).text('Check elevation data');
    };

    var show = function(r) {
        var missing = Math.max(0, r.wanted - r.have);
        var radius = r.radius_km + ' km';

        if (!r.wanted) {
            say('No elevation data needed for a radius of ' + radius + '.');
            stopPolling();
            return;
        }

        if (!missing) {
            say('Complete: ' + r.have + ' of ' + r.wanted + ' tiles for ' + radius +
                 ' around the receiver, ' + megabyte(r.bytes) + ' on disk.', 'text-success');
            stopPolling();
            return;
        }

        var text = r.have + ' of ' + r.wanted + ' tiles for ' + radius + ' around the receiver' +
                    (r.bytes ? ', ' + megabyte(r.bytes) + ' on disk' : '') + '. ' +
                    missing + ' missing';
        if (downloading) {
            say(text + ' - downloading, this line refreshes every few seconds. ' +
                 'It is safe to leave the page: the download carries on.');
        } else {
            // A tile that is all sea has nothing to download and will stay
            // "missing" for good, so the count never reaching zero is not
            // necessarily a failure.
            say(text + ', roughly ' + megabyte(missing * 8.4e6) + ' to fetch. ' +
                 'Tiles that are entirely sea do not exist and stay missing.');
            $button.text('Download ' + missing + ' missing tiles')
                     .removeClass('btn-secondary').addClass('btn-primary');
        }
    };

    $button.on('click', function() {
        if (downloading) return;
        var download = $button.hasClass('btn-primary');
        if (!download) {
            say('Checking...');
            ask(null);
            return;
        }
        downloading = true;
        $button.prop('disabled', true).text('Downloading...')
                 .removeClass('btn-primary').addClass('btn-secondary');
        say('Starting the download...');
        ask('download');
        timer = setInterval(function() { ask(null); }, 5000);
    });

    // The state on arrival, so an incomplete set is visible without being
    // asked for - the whole point of putting this on the page that holds the
    // location and the radius.
    ask(null);

    // A radius changed but not yet saved makes the figures above stale.
    $field.on('input', function() {
        if (downloading) return;
        say('Radius changed. Press "Apply and save", then check again - the figures ' +
             'above are for the saved radius.');
        $button.text('Check elevation data')
                 .removeClass('btn-primary').addClass('btn-secondary');
    });
});
