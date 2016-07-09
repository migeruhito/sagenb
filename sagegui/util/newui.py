# New UI
from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

from time import strftime
from time import time

from .templates import prettify_time_ago


def extended_wst_basic(wst, nb):
    d = wst.basic
    d.update({
        'last_change_pretty': prettify_time_ago(time() - wst.last_edited),
        'filename': wst.filename,
        'running': wst.compute_process_has_been_started(),
        'attached_data_files': wst.attached_data_files,
        'published': wst.published_id_number is not None,
        })
    if d['published']:
        d['published_time'] = strftime(
            "%B %d, %Y %I:%M %p",
            nb.filename_wst(wst.published_id_number).date_edited)
# New UI end
