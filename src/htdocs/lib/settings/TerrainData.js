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
    var $campo = $('#terrain_radius_km');
    if (!$campo.length) return;

    var $nota = $('<small class="d-block text-muted mt-1"></small>');
    var $pulsante = $('<button type="button" class="btn btn-sm btn-secondary mt-1">' +
                      'Check elevation data</button>');
    // The field sits inside an input-group because of its "km" suffix, so the
    // button goes after that group rather than after the input itself, where
    // it would be drawn as part of the group.
    var $gruppo = $campo.closest('.input-group');
    ($gruppo.length ? $gruppo : $campo).after($nota).after($pulsante);

    var timer = null;
    var scaricando = false;

    var dice = function(testo, classe) {
        $nota.removeClass('text-success text-danger text-muted')
             .addClass(classe || 'text-muted').html(testo);
    };

    var megabyte = function(b) {
        return Math.round(b / 1e6) + ' MB';
    };

    var chiedi = function(azione, allaFine) {
        return $.ajax({
            url: 'bookmarkimport/terrain', type: 'POST',
            data: JSON.stringify(azione ? {action: azione} : {}),
            contentType: 'application/json', dataType: 'json'
        }).done(function(r) {
            mostra(r);
            if (allaFine) allaFine(r);
        }).fail(function(xhr) {
            var messaggio = 'Could not check the elevation data.';
            try { messaggio = JSON.parse(xhr.responseText).error || messaggio; } catch (e) {}
            dice(messaggio, 'text-danger');
            fermaPolling();
        });
    };

    var fermaPolling = function() {
        if (timer) { clearInterval(timer); timer = null; }
        scaricando = false;
        $pulsante.prop('disabled', false).text('Check elevation data');
    };

    var mostra = function(r) {
        var mancanti = Math.max(0, r.wanted - r.have);
        var raggio = r.radius_km + ' km';

        if (!r.wanted) {
            dice('No elevation data needed for a radius of ' + raggio + '.');
            fermaPolling();
            return;
        }

        if (!mancanti) {
            dice('Complete: ' + r.have + ' of ' + r.wanted + ' tiles for ' + raggio +
                 ' around the receiver, ' + megabyte(r.bytes) + ' on disk.', 'text-success');
            fermaPolling();
            return;
        }

        var testo = r.have + ' of ' + r.wanted + ' tiles for ' + raggio + ' around the receiver' +
                    (r.bytes ? ', ' + megabyte(r.bytes) + ' on disk' : '') + '. ' +
                    mancanti + ' missing';
        if (scaricando) {
            dice(testo + ' - downloading, this line refreshes every few seconds. ' +
                 'It is safe to leave the page: the download carries on.');
        } else {
            // A tile that is all sea has nothing to download and will stay
            // "missing" for good, so the count never reaching zero is not
            // necessarily a failure.
            dice(testo + ', roughly ' + megabyte(mancanti * 8.4e6) + ' to fetch. ' +
                 'Tiles that are entirely sea do not exist and stay missing.');
            $pulsante.text('Download ' + mancanti + ' missing tiles')
                     .removeClass('btn-secondary').addClass('btn-primary');
        }
    };

    $pulsante.on('click', function() {
        if (scaricando) return;
        var scarica = $pulsante.hasClass('btn-primary');
        if (!scarica) {
            dice('Checking...');
            chiedi(null);
            return;
        }
        scaricando = true;
        $pulsante.prop('disabled', true).text('Downloading...')
                 .removeClass('btn-primary').addClass('btn-secondary');
        dice('Starting the download...');
        chiedi('download');
        timer = setInterval(function() { chiedi(null); }, 5000);
    });

    // The state on arrival, so an incomplete set is visible without being
    // asked for - the whole point of putting this on the page that holds the
    // location and the radius.
    chiedi(null);

    // A radius changed but not yet saved makes the figures above stale.
    $campo.on('input', function() {
        if (scaricando) return;
        dice('Radius changed. Press "Apply and save", then check again - the figures ' +
             'above are for the saved radius.');
        $pulsante.text('Check elevation data')
                 .removeClass('btn-primary').addClass('btn-secondary');
    });
});
