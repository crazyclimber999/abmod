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

    var $all = $table.find('.bookmark-select-all');
    var $button = $('.bookmark-delete-selected');
    var $count = $('.bookmark-selected-count');

    var selectedRows = function() {
        return $table.find('.bookmark-select:checked').closest('tr');
    };

    var refresh = function() {
        var n = selectedRows().length;
        var total = $table.find('.bookmark-select').length;
        $button.prop('disabled', n === 0).text(
            n ? 'Delete the ' + n + ' selected' : 'Delete selected');
        $count.text(n ? n + ' of ' + total + ' selected' : '');
        // the header box reflects the rows rather than driving them: all,
        // none, or neither
        $all.prop('checked', n > 0 && n === total);
        $all.prop('indeterminate', n > 0 && n < total);
    };

    $all.on('change', function() {
        $table.find('.bookmark-select').prop('checked', this.checked);
        refresh();
    });

    $table.on('change', '.bookmark-select', refresh);

    // shift-click selects a range, the way a file manager does: with a few
    // hundred rows, ticking them one at a time is the thing being avoided
    var lastClicked = null;
    $table.on('click', '.bookmark-select', function(e) {
        var boxes = $table.find('.bookmark-select').toArray();
        var index = boxes.indexOf(this);
        if (e.shiftKey && lastClicked !== null && lastClicked !== index) {
            var from = Math.min(lastClicked, index), to = Math.max(lastClicked, index);
            var state = this.checked;
            for (var i = from; i <= to; i++) boxes[i].checked = state;
            refresh();
        }
        lastClicked = index;
    });

    $button.on('click', function() {
        var $rows = selectedRows();
        if (!$rows.length) return;

        var names = $rows.map(function() {
            return $(this).find('[data-editor=name]').text();
        }).get();
        var preview = names.slice(0, 5).join('\n');
        if (names.length > 5) preview += '\n... and ' + (names.length - 5) + ' more';
        if (!confirm('Delete these ' + names.length + ' bookmarks? This cannot be undone.\n\n' +
                     preview)) {
            return;
        }

        var ids = $rows.map(function() { return $(this).data('id'); }).get();
        var $b = $(this).prop('disabled', true).text('Deleting...');
        $.ajax({
            url: 'bookmarks/selected',
            type: 'POST',
            data: JSON.stringify({ids: ids}),
            contentType: 'application/json',
            dataType: 'json'
        }).done(function(r) {
            $rows.remove();
            refresh();
            $('.bookmark-bulk-status').removeClass('text-danger').addClass('text-success')
                .text('Deleted ' + r.removed + '. ' + r.total + ' bookmarks left.');
        }).fail(function(xhr) {
            var message = 'Could not delete them.';
            try { message = JSON.parse(xhr.responseText).error || message; } catch (e) {}
            $('.bookmark-bulk-status').removeClass('text-success').addClass('text-danger')
                .text(message);
        }).always(function() {
            $b.prop('disabled', false);
            refresh();
        });
    });

    refresh();
});
