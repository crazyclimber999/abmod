/*
 * Works out the APRS-IS passcode from the callsign, next to the field.
 *
 * The passcode is not a secret and not a password: it is a published checksum
 * of the callsign, which every APRS program computes for itself. People reach
 * for a website to get it, and a website asking for a callsign to hand back a
 * "password" invites pasting the wrong thing entirely - this receiver was once
 * configured with an aprs.fi account password in that field, which left the
 * igate connected but marked "unverified", silently discarding everything it
 * sent.
 *
 * Computed in the browser: nothing is sent anywhere.
 */
$(function() {
    var $field = $('#aprs_igate_password');
    if (!$field.length) return;

    // The SSID plays no part: N0CALL, N0CALL-1 and N0CALL-10 share one
    // passcode, the one belonging to the callsign itself.
    var passcodeFor = function(raw) {
        var call = String(raw || '').split('-')[0].toUpperCase().trim();
        if (!/^[A-Z0-9]{3,}$/.test(call)) return null;
        var code = 0x73E2;
        for (var i = 0; i < call.length; i += 2) {
            code ^= call.charCodeAt(i) << 8;
            if (i + 1 < call.length) code ^= call.charCodeAt(i + 1);
        }
        return code & 0x7FFF;
    };

    var $button = $('<button type="button" class="btn btn-sm btn-secondary ml-2">' +
                      'Work it out from the callsign</button>');
    var $note = $('<small class="d-block text-muted"></small>');
    $field.after($note).after($button);

    var currentCallsign = function() {
        var $call = $('#aprs_callsign');
        return $call.length ? $call.val() : '';
    };

    $button.on('click', function() {
        var call = currentCallsign();
        var passcode = passcodeFor(call);
        if (passcode === null) {
            $note.removeClass('text-success').addClass('text-danger')
                 .text('Fill in the station callsign above first.');
            return;
        }
        $field.val(passcode);
        var base = String(call).split('-')[0].toUpperCase().trim();
        $note.removeClass('text-danger').addClass('text-success')
             .text('Passcode for ' + base + ': ' + passcode +
                   '. The SSID makes no difference - the same number covers ' +
                   base + ', ' + base + '-1 and so on. Remember to save.');
    });

    // A quiet warning for the mistake this button exists to prevent.
    $field.on('change', function() {
        var value = String($field.val() || '').trim();
        if (value && !/^[0-9]{1,6}$/.test(value)) {
            $note.removeClass('text-success').addClass('text-danger')
                 .text('That does not look like a passcode. It is a number of a few digits, ' +
                       'not a website password - with the wrong one the server accepts the ' +
                       'connection, marks it unverified, and discards everything sent.');
        } else {
            $note.text('');
        }
    });
});
