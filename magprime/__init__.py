from os.path import join

import cherrypy
import uber
from uber.errors import HTTPRedirect
from uber.jinja import template_overrides
from uber.models import Attendee, Session
from uber.utils import mount_site_sections, static_overrides

from magprime._version import __version__  # noqa: F401
from .config import config


# These need to come last so they can make use of config properties
from magprime.utils import *  # noqa: F401,E402,F403
from magprime.models import *  # noqa: F401,E402,F403
from magprime.automated_emails import *  # noqa: F401,E402,F403
from magprime.model_checks import *  # noqa: F401,E402,F403
from magprime.forms import *  # noqa: F401,E402,F403

# Silence pyflakes
from magprime.models import PrevSeasonSupporter  # noqa: E402


@Session.model_mixin
class SessionMixin:
    def season_pass(self, id):
        pss = self.query(PrevSeasonSupporter).filter_by(id=id).all()
        if pss:
            return pss[0]
        else:
            attendee = self.attendee(id)
            assert attendee.amount_extra >= c.SEASON_LEVEL
            return attendee

    def season_passes(self):
        attendees = {a.email: a for a in self.query(Attendee).filter(Attendee.amount_extra >= c.SEASON_LEVEL).all()}
        prev = [pss for pss in self.query(PrevSeasonSupporter).all() if pss.email not in attendees]
        return prev + list(attendees.values())


mount_site_sections(config['module_root'])

if c.AT_THE_CON:
    from uber.site_sections.preregistration import Root

    @cherrypy.expose
    def form(self, *args, **kwargs):
        raise HTTPRedirect('../registration/register')
    Root.form = form

# override badge CSV exports for magfest prime specific settings.
# magfest prime no longer uses one-day badges, so remove it.
_badge_exports = uber.site_sections.badge_exports.Root
_badge_exports.badge_zipfile_contents = \
    [fn for fn in _badge_exports.badge_zipfile_contents if fn.__name__ is not 'printed_badges_one_day']

static_overrides(join(config['module_root'], 'static'))
template_overrides(join(config['module_root'], 'templates'))
mount_site_sections(config['module_root'])