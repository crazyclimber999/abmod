/*
 * Selecting bookmarks and deleting them together.
 *
 * Kept apart from BookmarkTable.js, which is upstream's and handles editing a
 * row at a time: nothing here changes how a single bookmark behaves.
 *
 * A list that has had a repeater list imported into it runs to several
 * hundred rows, and removing a region's worth of them one button at a time is
 * not realistic. The deletion goes to the server as one request.
 */
$(function() {
    var $table = $('table.bookmark-table');
    if (!$table.length) return;

    var $tutti = $table.find('.bookmark-select-all');
    var $pulsante = $('.bookmark-delete-selected');
    var $conteggio = $('.bookmark-selected-count');

    var selezionate = function() {
        return $table.find('.bookmark-select:checked').closest('tr');
    };

    var aggiorna = function() {
        var n = selezionate().length;
        var totale = $table.find('.bookmark-select').length;
        $pulsante.prop('disabled', n === 0).text(
            n ? 'Delete the ' + n + ' selected' : 'Delete selected');
        $conteggio.text(n ? n + ' of ' + totale + ' selected' : '');
        // the header box reflects the rows rather than driving them: all,
        // none, or neither
        $tutti.prop('checked', n > 0 && n === totale);
        $tutti.prop('indeterminate', n > 0 && n < totale);
    };

    $tutti.on('change', function() {
        $table.find('.bookmark-select').prop('checked', this.checked);
        aggiorna();
    });

    $table.on('change', '.bookmark-select', aggiorna);

    // shift-click selects a range, the way a file manager does: with a few
    // hundred rows, ticking them one at a time is the thing being avoided
    var ultima = null;
    $table.on('click', '.bookmark-select', function(e) {
        var caselle = $table.find('.bookmark-select').toArray();
        var indice = caselle.indexOf(this);
        if (e.shiftKey && ultima !== null && ultima !== indice) {
            var da = Math.min(ultima, indice), a = Math.max(ultima, indice);
            var stato = this.checked;
            for (var i = da; i <= a; i++) caselle[i].checked = stato;
            aggiorna();
        }
        ultima = indice;
    });

    $pulsante.on('click', function() {
        var $righe = selezionate();
        if (!$righe.length) return;

        var nomi = $righe.map(function() {
            return $(this).find('[data-editor=name]').text();
        }).get();
        var anteprima = nomi.slice(0, 5).join('\n');
        if (nomi.length > 5) anteprima += '\n... and ' + (nomi.length - 5) + ' more';
        if (!confirm('Delete these ' + nomi.length + ' bookmarks? This cannot be undone.\n\n' +
                     anteprima)) {
            return;
        }

        var ids = $righe.map(function() { return $(this).data('id'); }).get();
        var $b = $(this).prop('disabled', true).text('Deleting...');
        $.ajax({
            url: 'bookmarks/selected',
            type: 'POST',
            data: JSON.stringify({ids: ids}),
            contentType: 'application/json',
            dataType: 'json'
        }).done(function(r) {
            $righe.remove();
            aggiorna();
            $('.bookmark-bulk-status').removeClass('text-danger').addClass('text-success')
                .text('Deleted ' + r.removed + '. ' + r.total + ' bookmarks left.');
        }).fail(function(xhr) {
            var messaggio = 'Could not delete them.';
            try { messaggio = JSON.parse(xhr.responseText).error || messaggio; } catch (e) {}
            $('.bookmark-bulk-status').removeClass('text-success').addClass('text-danger')
                .text(messaggio);
        }).always(function() {
            $b.prop('disabled', false);
            aggiorna();
        });
    });

    aggiorna();
});
