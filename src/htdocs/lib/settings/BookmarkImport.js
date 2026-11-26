/*
 * Importing a repeater list into the bookmarks.
 *
 * The server hands over the spreadsheet as a plain table of strings and takes
 * back a finished list of bookmarks. Everything in between happens here: which
 * column means what, which regions to take, and how the source spells its
 * modulations. Published lists do not agree on any of that, so none of it is
 * assumed - the file is only ever a starting guess that the operator corrects.
 */
$(function() {
    var $page = $('#bookmark-import');
    if (!$page.length) return;

    var modes = $page.data('modes') || {};
    // listed but not selectable, so it is plain why DMR cannot be chosen here
    var unavailableModes = $page.data('unavailable-modes') || {};
    var setup = $page.data('importsetup') || {};
    var modmap = setup.modmap || $page.data('modmap') || {};
    var fallbackDefault = setup.fallback || $page.data('fallback') || 'nfm';
    $page.find('.import-url').val(setup.url || '');

    // The listenability settings are applied here as well as after a file is
    // loaded. buildMapping() runs only once there is a file, so until then the
    // fields still showed whatever the template hard-codes - which made a
    // saved default of 20 dB look as though it had not been stored at all.
    var applyReach = function(from) {
        var r = (from || setup).reach || {};
        if (r.margin !== undefined) $page.find('.import-reach-margin').val(r.margin);
        if (r.distance !== undefined) $page.find('.import-reach-distance').val(r.distance);
        $page.find('.import-reach-horizon').prop('checked', r.horizon === true);
        $page.find('.import-reach-nearest').prop('checked', r.nearest === true);
    };
    applyReach();
    var SKIP = '__skip__';
    var table = null;      // {columns, rows}
    var PREVIEW_ROWS = 25;
    // which page of the preview is on screen. Reset whenever the rows
    // themselves change, kept when only the page is turned.
    var page = 0;

    // published lists differ in case and padding, so the remembered mapping is
    // keyed on a normalised form
    var normalise = function(value) {
        return (value === null || value === undefined ? '' : String(value)).trim().toUpperCase();
    };

    var $status = $page.find('.import-status');
    var $mapping = $page.find('.import-mapping');

    var setStatus = function(text, kind) {
        $status.removeClass('text-danger text-success').text(text || '');
        if (kind) $status.addClass(kind === 'error' ? 'text-danger' : 'text-success');
    };

    /* ---------------------------------------------------------------- load */

    var load = function(request) {
        setStatus('Reading the file...');
        $mapping.hide();
        request.done(function(data) {
            table = data;
            if (setup.headerRow !== undefined) {
                $mapping.find('.import-header-row').val(setup.headerRow);
            }
            setStatus('Read ' + data.rows.length + ' rows, ' + data.columns.length + ' columns.');
            buildMapping();
            $mapping.show();
        }).fail(function(xhr) {
            var message = 'Could not read the file.';
            try { message = JSON.parse(xhr.responseText).error || message; } catch (e) {}
            setStatus(message, 'error');
        });
    };

    $page.find('.import-from-url').on('click', function() {
        var url = $page.find('.import-url').val().trim();
        if (!url) { setStatus('Enter a URL first.', 'error'); return; }
        load($.ajax({
            url: 'bookmarkimport/parse?url=' + encodeURIComponent(url),
            type: 'POST',
            dataType: 'json'
        }));
    });

    $page.find('.import-from-file').on('click', function() {
        var file = $page.find('.import-file')[0].files[0];
        if (!file) { setStatus('Choose a file first.', 'error'); return; }
        load($.ajax({
            url: 'bookmarkimport/parse?filename=' + encodeURIComponent(file.name),
            type: 'POST',
            data: file,
            processData: false,
            contentType: 'application/octet-stream',
            dataType: 'json'
        }));
    });

    /* ------------------------------------------------------------- mapping */

    var headerRow = function() {
        return parseInt($mapping.find('.import-header-row').val(), 10) || 0;
    };

    var columnName = function(index) {
        var header = '';
        if (table.rows[headerRow()]) header = (table.rows[headerRow()][index] || '').trim();
        var label = table.columns[index].label;
        return header ? label + ' - ' + header : label;
    };

    var columnOptions = function(allowNone) {
        var out = allowNone ? '<option value="-1">(none)</option>' : '';
        table.columns.forEach(function(c) {
            out += '<option value="' + c.index + '">' + $('<div>').text(columnName(c.index)).html() + '</option>';
        });
        return out;
    };

    // A first guess from the header text; every published list words these
    // differently, which is exactly why the dropdowns exist. The patterns
    // below include Italian spellings - nome, regione, provincia, nominativo -
    // because the lists this was written against are Italian. They are header
    // text to match, not language: add your own and the guess improves.
    var guess = function(patterns, fallback) {
        var header = table.rows[headerRow()] || [];
        for (var i = 0; i < header.length; i++) {
            var text = (header[i] || '').toLowerCase();
            for (var p = 0; p < patterns.length; p++) {
                if (text.indexOf(patterns[p]) > -1) return i;
            }
        }
        return fallback;
    };

    var buildMapping = function() {
        var $fields = $mapping.find('.import-fields');
        $fields.html(
            field('Name, first part', 'name1', columnOptions(true)) +
            textField('Joined by', 'separator', ' - ') +
            field('Name, second part', 'name2', columnOptions(true)) +
            field('Frequency', 'frequency', columnOptions(false)) +
            field('Frequency unit', 'unit',
                '<option value="1">Hz</option><option value="1000">kHz</option><option value="1000000">MHz</option>') +
            field('Modulation', 'modulation', columnOptions(true)) +
            field('Region', 'region', columnOptions(true)) +
            field('Locator', 'locator', columnOptions(true))
        );

        $mapping.find('[data-field=name1]').val(guess(['id', 'call', 'nominativ'], -1));
        $mapping.find('[data-field=name2]').val(guess(['nome', 'name', 'localit'], -1));
        $mapping.find('[data-field=frequency]').val(guess(['freq', 'qrg'], 0));
        $mapping.find('[data-field=modulation]').val(guess(['grp', 'mod', 'mode'], -1));
        $mapping.find('[data-field=region]').val(guess(['region', 'regione', 'provincia'], -1));
        // the locator is what the listenability estimate needs: it is the only
        // thing in a repeater list that says where the station actually is
        $mapping.find('[data-field=locator]').val(guess(['loc', 'qra', 'grid'], -1));
        $mapping.find('[data-field=unit]').val(guessUnit());

        // The saved setup overrides the guesses, but only where it still fits
        // this file: a column index past the end belongs to a different layout
        // and the guess is the better answer.
        var fields = setup.fields || {};
        $.each(fields, function(fieldName, value) {
            var $el = $mapping.find('[data-field=' + fieldName + ']');
            if (!$el.length) return;
            if (fieldName === 'separator' || fieldName === 'unit') { $el.val(value); return; }
            var index = parseInt(value, 10);
            if (isNaN(index) || index >= table.columns.length) return;
            $el.val(index);
        });

        buildExtras();
        (setup.extras || []).forEach(function(i) {
            $mapping.find('.import-extra[value="' + i + '"]').prop('checked', true);
        });
        buildRegions();
        // only when something was saved: otherwise every region stays ticked,
        // which is the right default for a file never imported before
        if ((setup.regions || []).length) {
            var wantedRegions = {};
            setup.regions.forEach(function(r) { wantedRegions[r] = true; });
            $mapping.find('.import-region').each(function() {
                $(this).prop('checked', !!wantedRegions[this.value]);
            });
        }
        buildModulations();

        // the listenability settings are remembered like everything else
        applyReach();

        page = 0;
        refresh();
    };

    var field = function(label, name, options) {
        return '<div class="form-group row">' +
            '<label class="col-form-label col-sm-4">' + label + '</label>' +
            '<div class="col-sm-8"><select class="form-control" data-field="' + name + '">' + options + '</select></div>' +
            '</div>';
    };

    var textField = function(label, name, value) {
        return '<div class="form-group row">' +
            '<label class="col-form-label col-sm-4">' + label + '</label>' +
            '<div class="col-sm-8"><input type="text" class="form-control" data-field="' + name + '" value="' + value + '"></div>' +
            '</div>';
    };

    var col = function(name) {
        var $el = $mapping.find('[data-field=' + name + ']');
        return $el.length ? parseInt($el.val(), 10) : -1;
    };

    var cell = function(row, index) {
        if (index < 0 || !row) return '';
        return (row[index] || '').trim();
    };

    var dataRows = function() {
        return table.rows.slice(headerRow() + 1);
    };

    // a frequency column may hold Hz, kHz or MHz; the magnitude says which
    var guessUnit = function() {
        var index = guess(['freq', 'qrg'], 0);
        var values = [];
        dataRows().forEach(function(r) {
            var v = parseFloat((r[index] || '').replace(',', '.'));
            if (!isNaN(v) && v > 0) values.push(v);
        });
        if (!values.length) return '1000';
        values.sort(function(a, b) { return a - b; });
        var median = values[Math.floor(values.length / 2)];
        if (median > 10000000) return '1';
        if (median > 10000) return '1000';
        return '1000000';
    };

    /* -------------------------------------------------------------- extras */

    var buildExtras = function() {
        var html = '';
        table.columns.forEach(function(c) {
            html += '<label class="mr-3"><input type="checkbox" class="import-extra" value="' + c.index + '"> ' +
                $('<div>').text(columnName(c.index)).html() + '</label>';
        });
        $mapping.find('.import-extras').html(html);
    };

    var extras = function() {
        return $mapping.find('.import-extra:checked').map(function() {
            return parseInt(this.value, 10);
        }).get();
    };

    /* ------------------------------------------------------------- regions */

    var buildRegions = function() {
        var index = col('region');
        var $box = $mapping.find('.import-regions');
        if (index < 0) {
            $box.html('<div class="text-muted">No region column selected: every row will be imported.</div>');
            return;
        }
        var counts = {};
        dataRows().forEach(function(r) {
            var v = cell(r, index);
            if (v) counts[v] = (counts[v] || 0) + 1;
        });
        var names = Object.keys(counts).sort();
        var html = '<div class="mb-2">' +
            '<button type="button" class="btn btn-sm btn-secondary import-regions-all">Select all</button> ' +
            '<button type="button" class="btn btn-sm btn-secondary import-regions-none">Select none</button></div>';
        names.forEach(function(n) {
            html += '<label class="mr-3"><input type="checkbox" class="import-region" checked value="' +
                $('<div>').text(n).html() + '"> ' + $('<div>').text(n).html() +
                ' <span class="text-muted">(' + counts[n] + ')</span></label>';
        });
        $box.html(html);
    };

    var selectedRegions = function() {
        var out = {};
        $mapping.find('.import-region:checked').each(function() { out[this.value] = true; });
        return out;
    };

    /* --------------------------------------------------------- modulations */

    var buildModulations = function() {
        var index = col('modulation');
        var $box = $mapping.find('.import-modulations');
        var options = '';
        $.each(modes, function(modulation, name) {
            options += '<option value="' + modulation + '">' + $('<div>').text(name).html() + '</option>';
        });
        var unavailable = '';
        $.each(unavailableModes, function(modulation, name) {
            unavailable += '<option value="" disabled>' + $('<div>').text(name).html() +
                ' - not available on this receiver</option>';
        });
        if (unavailable) {
            unavailable = '<optgroup label="Needs a codec this receiver does not have">' +
                unavailable + '</optgroup>';
        }

        var fallback = '<div class="form-group row">' +
            '<label class="col-form-label col-sm-4">Used when nothing matches</label>' +
            '<div class="col-sm-8"><select class="form-control import-fallback">' + options + '</select></div></div>' +
            '<div class="import-modmap-note text-muted mb-2"></div>' +
            '<button type="button" class="btn btn-secondary import-save-defaults">' +
                'Save this whole setup as the default</button> ' +
            '<button type="button" class="btn btn-secondary import-reset-defaults">' +
                'Back to the built-in setup</button> ' +
            '<span class="import-defaults-status text-muted"></span>';

        if (index < 0) {
            $box.html('<div class="text-muted mb-2">No modulation column selected: every bookmark gets the ' +
                'modulation below.</div>' + fallback);
        } else {
            var values = {};
            dataRows().forEach(function(r) {
                var v = cell(r, index);
                values[v] = (values[v] || 0) + 1;
            });
            var html = '<div class="text-muted mb-2">The source does not use our modulation names, so each value ' +
                'it contains is translated here. This table is meant to be adjusted.</div>' +
                '<table class="table table-sm"><tr><th>In the file</th><th>Rows</th><th>Becomes</th></tr>';
            Object.keys(values).sort().forEach(function(v) {
                html += '<tr><td>' + (v ? $('<div>').text(v).html() : '<em>(empty)</em>') + '</td>' +
                    '<td>' + values[v] + '</td>' +
                    '<td><select class="form-control form-control-sm import-modmap" data-source="' +
                    $('<div>').text(v).html() + '">' +
                    '<option value="">(use the default below)</option>' +
                    '<option value="' + SKIP + '">(ignore import)</option>' +
                    options + unavailable + '</select></td></tr>';
            });
            html += '</table>' + fallback;
            $box.html(html);

            // The preselection comes from the remembered mapping, which starts
            // as the one worked out from the ik2ane legend. A value it does not
            // know is left for the operator to decide.
            var unknown = [];
            $box.find('.import-modmap').each(function() {
                var source = normalise($(this).data('source'));
                if (!(source in modmap)) {
                    if (source) unknown.push(source);
                    return;
                }
                var target = modmap[source];
                // a remembered mode that is no longer available would silently
                // drop every one of its rows at import time, so it is shown as
                // "do not import" instead, which is what would happen anyway
                if (target && target !== SKIP && !modes[target]) target = SKIP;
                $(this).val(target);
            });
            if (unknown.length) {
                $box.find('.import-modmap-note').text(
                    'Not in the saved mapping, so left unset: ' + unknown.join(', ') + '.');
            }
        }

        var chosen = modes[fallbackDefault] ? fallbackDefault : 'nfm';
        if (modes[chosen]) $box.find('.import-fallback').val(chosen);
    };

    /* ------------------------------------------- remembering the mapping */

    var currentMapping = function() {
        var out = {};
        $mapping.find('.import-modmap').each(function() {
            out[normalise($(this).data('source'))] = $(this).val();
        });
        return out;
    };

    var defaultsStatus = function(text, kind) {
        $mapping.find('.import-defaults-status')
            .removeClass('text-danger text-success').text(text || '');
        if (kind) {
            $mapping.find('.import-defaults-status')
                .addClass(kind === 'error' ? 'text-danger' : 'text-success');
        }
    };

    // everything the page knows, so the next import starts where this one
    // ended instead of from the built-in guesses
    var currentSetup = function() {
        var fields = {};
        ['name1', 'name2', 'separator', 'frequency', 'unit', 'modulation', 'region', 'locator']
            .forEach(function(fieldName) {
                var $el = $mapping.find('[data-field=' + fieldName + ']');
                if ($el.length) fields[fieldName] = $el.val();
            });
        return {
            url: $page.find('.import-url').val().trim(),
            headerRow: headerRow(),
            fields: fields,
            extras: extras(),
            regions: $mapping.find('.import-region:checked').map(function() {
                return this.value;
            }).get(),
            modmap: currentMapping(),
            fallback: $mapping.find('.import-fallback').val(),
            reach: {
                margin: parseFloat($mapping.find('.import-reach-margin').val()),
                distance: parseFloat($mapping.find('.import-reach-distance').val()),
                horizon: $mapping.find('.import-reach-horizon').is(':checked'),
                nearest: $mapping.find('.import-reach-nearest').is(':checked')
            }
        };
    };

    $mapping.on('click', '.import-save-defaults', function() {
        var toSave = currentSetup();
        defaultsStatus('Saving...');
        $.ajax({
            url: 'bookmarkimport/defaults',
            type: 'POST',
            data: JSON.stringify(toSave),
            contentType: 'application/json',
            dataType: 'json'
        }).done(function(r) {
            setup = toSave;
            modmap = toSave.modmap;
            fallbackDefault = r.fallback;
            defaultsStatus('Saved: source, columns, ' + r.regions + ' regions and ' +
                r.saved + ' modulations. The next import starts from this.', 'ok');
        }).fail(function(xhr) {
            var message = 'Could not save the mapping.';
            try { message = JSON.parse(xhr.responseText).error || message; } catch (e) {}
            defaultsStatus(message, 'error');
        });
    });

    $mapping.on('click', '.import-reset-defaults', function() {
        defaultsStatus('Restoring...');
        $.ajax({url: 'bookmarkimport/resetdefaults', type: 'POST', dataType: 'json'})
            .done(function(r) {
                setup = r;
                modmap = {};
                $.each(r.modmap || {}, function(k, v) { modmap[normalise(k)] = v; });
                fallbackDefault = r.fallback;
                $page.find('.import-url').val(r.url || '');
                applyReach(r);
                buildModulations();
                page = 0;
                refresh();
                defaultsStatus('Back to the built-in setup.', 'ok');
            })
            .fail(function() { defaultsStatus('Could not restore the mapping.', 'error'); });
    });

    // returns null for rows the operator chose to leave out entirely, which is
    // the sensible answer for repeaters this receiver cannot demodulate at all
    var modulationFor = function(value) {
        var mapped = $mapping.find('.import-modmap[data-source="' + value.replace(/"/g, '\\"') + '"]').val();
        if (mapped === '__skip__') return null;
        if (mapped) return mapped;
        return $mapping.find('.import-fallback').val();
    };

    /* --------------------------------------------- can it be heard at all */

    // one entry per data row, filled in by the server; null until worked out
    var reach = null;

    var reachStatus = function(text, kind) {
        $mapping.find('.import-reach-status')
            .removeClass('text-danger text-success').text(text || '');
        if (kind) {
            $mapping.find('.import-reach-status')
                .addClass(kind === 'error' ? 'text-danger' : 'text-success');
        }
    };

    // the operator's choice at step 6: import everything, or only what the
    // terrain says can be heard. Nothing is filtered until the paths have
    // actually been measured, so a half-finished estimate cannot quietly
    // throw rows away.
    var reachWanted = function() {
        return $mapping.find('.import-reach-mode:checked').val() === 'reach';
    };

    var reachOn = function() {
        return reachWanted() && reach !== null;
    };

    // true when this row survives the listenability filter
    var reachKeeps = function(index) {
        if (!reachOn()) return true;
        var r = reach[index];
        if (!r || r.status !== 'ok') return false;
        var minMargin = parseFloat($mapping.find('.import-reach-margin').val());
        var maxDistance = parseFloat($mapping.find('.import-reach-distance').val());
        if (!isNaN(maxDistance) && r.distance_km > maxDistance) return false;
        if (r.beyond_horizon && !$mapping.find('.import-reach-horizon').is(':checked')) return false;
        if (!isNaN(minMargin) && r.margin_db < minMargin) return false;
        return true;
    };

    $mapping.on('change', '.import-reach-mode', function() {
        var wanted = reachWanted();
        $mapping.find('.import-reach-options').toggle(wanted);
        if (wanted && reach === null) {
            reachStatus('Press "Work it out" to measure the paths.');
        }
        if (!wanted) reachStatus('');
        refresh();
    });

    $mapping.on('click', '.import-reach-run', function() {
        var iLoc = col('locator'), iFreq = col('frequency');
        if (iLoc < 0) {
            reachStatus('Say which column holds the locator first, under step 2.', 'error');
            return;
        }
        var unit = parseFloat($mapping.find('[data-field=unit]').val()) || 1;
        var tableRows = dataRows();
        var entries = tableRows.map(function(row) {
            var raw = cell(row, iFreq).replace(/\s/g, '').replace(',', '.');
            var f = parseFloat(raw);
            return {
                locator: cell(row, iLoc),
                frequency: isNaN(f) ? 0 : Math.round(f * unit)
            };
        });

        var $b = $(this).prop('disabled', true);
        reachStatus('Measuring ' + entries.length + ' paths...');
        $.ajax({
            url: 'bookmarkimport/propagation',
            type: 'POST',
            data: JSON.stringify({entries: entries}),
            contentType: 'application/json',
            dataType: 'json'
        }).done(function(r) {
            reach = r.results || [];
            var ok = 0, noLocator = 0, noTerrain = 0, beyond = 0;
            reach.forEach(function(x) {
                if (!x || x.status === 'no_locator') noLocator++;
                else if (x.status === 'no_terrain') noTerrain++;
                else { ok++; if (x.beyond_horizon) beyond++; }
            });
            var text = ok + ' paths measured';
            if (beyond) text += ', ' + beyond + ' beyond the horizon';
            if (noLocator) text += ', ' + noLocator + ' without a locator';
            if (noTerrain) text += ', ' + noTerrain + ' outside the elevation data';
            reachStatus(text + '.', 'ok');
            page = 0;
            refresh();
        }).fail(function(xhr) {
            var message = 'Could not measure the paths.';
            try { message = JSON.parse(xhr.responseText).error || message; } catch (e) {}
            reachStatus(message, 'error');
        }).always(function() {
            $b.prop('disabled', false);
        });
    });

    $mapping.on('click', '.import-terrain-check', function() {
        reachStatus('Checking the elevation data...');
        $.ajax({
            url: 'bookmarkimport/terrain', type: 'POST',
            data: JSON.stringify({}), contentType: 'application/json', dataType: 'json'
        }).done(function(r) {
            if (r.have >= r.wanted) {
                reachStatus('Elevation data complete: ' + r.have + ' tiles, ' +
                    Math.round(r.bytes / 1e6) + ' MB, ' + r.radius_km + ' km around the receiver.', 'ok');
                return;
            }
            var missing = r.wanted - r.have;
            if (!confirm('Missing ' + missing + ' of ' + r.wanted + ' elevation tiles for ' +
                    r.radius_km + ' km around the receiver.\n\nDownload them now? ' +
                    'That is roughly ' + Math.round(missing * 8.4) + ' MB.')) {
                return;
            }
            $.ajax({
                url: 'bookmarkimport/terrain', type: 'POST',
                data: JSON.stringify({action: 'download'}),
                contentType: 'application/json', dataType: 'json'
            }).done(function() {
                reachStatus('Downloading in the background. Press this again to see how far it got.');
            });
        }).fail(function(xhr) {
            var message = 'Could not check the elevation data.';
            try { message = JSON.parse(xhr.responseText).error || message; } catch (e) {}
            reachStatus(message, 'error');
        });
    });

    /* ----------------------------------------------------------- the rows */

    // ignoreReach serves the count under the preview: the same rows built as
    // if the listenability filter were switched off, so the page can say how
    // many it is leaving out instead of just showing fewer.
    var build = function(ignoreReach) {
        var out = [];
        if (!table) return out;

        var iName1 = col('name1'), iName2 = col('name2'), iFreq = col('frequency');
        var iMod = col('modulation'), iRegion = col('region');
        var separator = $mapping.find('[data-field=separator]').val() || ' ';
        var unit = parseFloat($mapping.find('[data-field=unit]').val()) || 1;
        var regions = selectedRegions();
        var filterRegions = iRegion >= 0;
        var extraColumns = extras();

        dataRows().forEach(function(row, index) {
            if (filterRegions && !regions[cell(row, iRegion)]) return;
            if (!ignoreReach && !reachKeeps(index)) return;

            var raw = cell(row, iFreq).replace(/\s/g, '').replace(',', '.');
            var frequency = parseFloat(raw);
            if (isNaN(frequency) || frequency <= 0) return;
            frequency = Math.round(frequency * unit);

            var parts = [];
            if (iName1 >= 0 && cell(row, iName1)) parts.push(cell(row, iName1));
            if (iName2 >= 0 && cell(row, iName2)) parts.push(cell(row, iName2));
            var name = parts.join(separator);

            var suffix = extraColumns.map(function(i) { return cell(row, i); })
                .filter(function(v) { return v; });
            if (suffix.length) name += ' [' + suffix.join(', ') + ']';
            if (!name) name = 'Unnamed';

            var modulation = modulationFor(iMod >= 0 ? cell(row, iMod) : '');
            if (modulation === null) return;

            var entry = {
                name: name.substring(0, 120),
                frequency: frequency,
                modulation: modulation
            };
            // carried for the preview only; the import endpoint ignores it
            if (reachOn() && reach[index]) entry.reach = reach[index];
            out.push(entry);
        });

        // One channel, one bookmark. A national repeater list reuses the same
        // frequency dozens of times over, and from any one place only one of
        // them is the station actually heard there; the rest would be
        // bookmarks that tune to somebody else's repeater.
        //
        // The one kept is the one with the most signal left, not the closest.
        // They usually agree, but not always: on 144.650 the nearest repeater
        // is 10 km closer and 20 dB weaker than one standing on a mountain,
        // and it is the mountain that is heard.
        //
        // This needs the path budget, which only exists once the paths have
        // been measured, so the option lives with the listenability settings.
        if (!ignoreReach && reachOn() && $mapping.find('.import-reach-nearest').is(':checked')) {
            var best = {};
            out.forEach(function(b, i) {
                var k = b.frequency + '|' + b.modulation;
                var m = (b.reach && b.reach.margin_db !== undefined) ? b.reach.margin_db : -Infinity;
                if (!(k in best) || m > best[k].m) best[k] = {m: m, i: i};
            });
            var keep = {};
            $.each(best, function(k, v) { keep[v.i] = true; });
            out = out.filter(function(b, i) { return keep[i]; });
        }

        return out;
    };

    var refresh = function() {
        var rows = build();
        var showReach = reachOn();
        var pageCount = Math.max(1, Math.ceil(rows.length / PREVIEW_ROWS));
        if (page >= pageCount) page = pageCount - 1;
        if (page < 0) page = 0;
        var first = page * PREVIEW_ROWS;
        var last = Math.min(first + PREVIEW_ROWS, rows.length);

        var html = '<table class="table table-sm"><tr><th>#</th><th>Name</th><th>Frequency</th>' +
            '<th>Modulation</th>' +
            (showReach ? '<th>Distance</th><th>Margin</th>' : '') + '</tr>';
        rows.slice(first, last).forEach(function(b, i) {
            html += '<tr><td class="text-muted">' + (first + i + 1) + '</td>';
            html += '<td>' + $('<div>').text(b.name).html() + '</td>' +
                '<td>' + (b.frequency / 1e6).toFixed(5) + ' MHz</td>' +
                '<td>' + $('<div>').text(b.modulation).html() + '</td>';
            if (showReach) {
                var r = b.reach || {};
                html += '<td>' + (r.distance_km !== undefined ? r.distance_km + ' km' : '-') + '</td>' +
                    '<td>' + (r.margin_db !== undefined ? r.margin_db + ' dB' : '-') +
                    (r.beyond_horizon ? ' <span class="text-muted">(beyond horizon)</span>' : '') +
                    '</td>';
            }
            html += '</tr>';
        });
        html += '</table>';

        // Every row that will be imported is reachable, a page at a time:
        // showing only the first 25 and stopping there hides whatever the
        // mapping did to the other thousand.
        if (rows.length > PREVIEW_ROWS) {
            html += '<div class="import-pager">' +
                '<button type="button" class="btn btn-sm btn-secondary import-page" data-to="first"' +
                    (page === 0 ? ' disabled' : '') + '>&laquo;</button> ' +
                '<button type="button" class="btn btn-sm btn-secondary import-page" data-to="prev"' +
                    (page === 0 ? ' disabled' : '') + '>&lsaquo;</button> ' +
                '<span class="mx-2">' + (first + 1) + '\u2013' + last + ' of ' + rows.length +
                '  (page ' + (page + 1) + ' of ' + pageCount + ')</span> ' +
                '<button type="button" class="btn btn-sm btn-secondary import-page" data-to="next"' +
                    (page >= pageCount - 1 ? ' disabled' : '') + '>&rsaquo;</button> ' +
                '<button type="button" class="btn btn-sm btn-secondary import-page" data-to="last"' +
                    (page >= pageCount - 1 ? ' disabled' : '') + '>&raquo;</button>' +
                '</div>';
        }

        $mapping.find('.import-preview').html(html);
        $mapping.find('.import-count').text(rows.length);
        // a filter that silently discards looks exactly like a broken import,
        // so the count of what it removed is always on screen
        // Two rows with the same name, frequency and modulation are the same
        // bookmark and only one is stored. In a national repeater list that is
        // easy to cause by accident: dozens of stations share a channel, so if
        // the name does not tell them apart they silently collapse into one.
        var seen = {}, duplicates = 0;
        rows.forEach(function(b) {
            var k = b.name.trim().toLowerCase() + '|' + b.frequency + '|' + b.modulation;
            if (seen[k]) duplicates++; else seen[k] = true;
        });
        $mapping.find('.import-collisions').text(
            duplicates
                ? duplicates + ' of these have the same name, frequency and modulation as another ' +
                  'and only one of each will be stored. Add a column that tells them apart - the ' +
                  'locality, under step 3 - to keep them all.'
                : '');

        if (showReach) {
            var unfiltered = build(true).length;
            $mapping.find('.import-reach-removed').text(
                unfiltered > rows.length
                    ? (unfiltered - rows.length) + ' of ' + unfiltered + ' left out as unlikely to be heard'
                    : '');
        } else {
            $mapping.find('.import-reach-removed').text('');
        }
        $mapping.find('.import-apply').prop('disabled', rows.length === 0);
    };

    $mapping.on('change', 'select, input', function() {
        if ($(this).hasClass('import-save-defaults')) return;
        // the rows themselves have changed, so the page you were on no longer
        // refers to anything
        page = 0;
        var field = $(this).data('field');
        // changing which column holds the region or the modulation changes
        // the lists built from that column's values
        if (field === 'region') buildRegions();
        if (field === 'modulation') buildModulations();
        if ($(this).hasClass('import-header-row')) { buildMapping(); return; }
        refresh();
    });

    $mapping.on('click', '.import-page', function() {
        var to = $(this).data('to');
        var pageCount = Math.max(1, Math.ceil(build().length / PREVIEW_ROWS));
        if (to === 'first') page = 0;
        else if (to === 'prev') page -= 1;
        else if (to === 'next') page += 1;
        else if (to === 'last') page = pageCount - 1;
        refresh();
    });

    $mapping.on('click', '.import-regions-all, .import-regions-none', function() {
        $mapping.find('.import-region').prop('checked', $(this).hasClass('import-regions-all'));
        page = 0;
        refresh();
    });

    /* -------------------------------------------------------------- import */

    $mapping.on('click', '.import-apply', function() {
        var rows = build().map(function(b) {
            return {name: b.name, frequency: b.frequency, modulation: b.modulation};
        });
        if (!rows.length) {
            $mapping.find('.import-result').removeClass('text-success')
                .addClass('text-danger')
                .text('Nothing to import: every row was filtered out by the steps above.');
            return;
        }
        var replace = $mapping.find('.import-replace').is(':checked');
        if (replace && !confirm('This throws away every bookmark currently stored, and cannot be undone. Continue?')) {
            return;
        }
        var $button = $(this).prop('disabled', true);
        // next to the button, not at the top of the page: the status line up
        // there is off screen by the time anyone reaches Import, so a finished
        // import looked exactly like nothing happening
        var report = function(text, kind) {
            setStatus(text, kind);
            $mapping.find('.import-result')
                .removeClass('text-danger text-success').text(text)
                .addClass(kind === 'error' ? 'text-danger' : 'text-success');
        };
        report('Importing ' + rows.length + ' bookmarks...');
        $.ajax({
            url: 'bookmarkimport/apply',
            type: 'POST',
            data: JSON.stringify({
                bookmarks: rows,
                replace: replace,
                replaceOnFrequency: $mapping.find('.import-replace-frequency').is(':checked')
            }),
            contentType: 'application/json',
            dataType: 'json'
        }).done(function(r) {
            var text = 'Imported: ' + r.added + ' added';
            if (r.replaced) text += ', ' + r.replaced + ' of your own replaced on the same frequency';
            if (r.updated) text += ', ' + r.updated + ' already there';
            if (r.skipped) text += ', ' + r.skipped + ' skipped';
            report(text + '. ' + r.total + ' bookmarks in storage.', 'ok');
        }).fail(function(xhr) {
            var message = 'The import failed.';
            try { message = JSON.parse(xhr.responseText).error || message; } catch (e) {}
            report(message, 'error');
        }).always(function() {
            $button.prop('disabled', false);
        });
    });
});
