from pockets.autolog import log
from residue import CoerceUTF8 as UnicodeText, UUID

from uber.config import c
from uber.decorators import presave_adjustment, render
from uber.models import Boolean, MagModel, Choice, DefaultColumn as Column, Session
from uber.tasks.email import send_email
from uber.utils import add_opt, check, localized_now, remove_opt


@Session.model_mixin
class Group:
    prior_name = Column(UnicodeText)

@Session.model_mixin
class Attendee:
    special_merch = Column(Choice(c.SPECIAL_MERCH_OPTS), default=c.NO_MERCH)
    agreed_to_covid_policies = Column(Boolean, default=False)
    group_name = Column(UnicodeText)
    covid_ready = Column(Boolean, default=False)
    donate_badge_cost = Column(Boolean, default=False)

    @presave_adjustment
    def invalid_notification(self):
        if self.staffing and self.badge_status == c.INVALID_STATUS \
                and self.badge_status != self.orig_value_of('badge_status'):
            try:
                send_email.delay(
                    c.STAFF_EMAIL,
                    c.STAFF_EMAIL,
                    'Volunteer invalidated',
                    render('emails/invalidated_volunteer.txt', {'attendee': self}, encoding=None),
                    model=self.to_dict('id'))
            except Exception:
                log.error('unable to send invalid email', exc_info=True)

    @presave_adjustment
    def child_badge(self):
        if self.age_now_or_at_con and self.age_now_or_at_con < 18 and self.badge_type == c.ATTENDEE_BADGE:
            self.badge_type = c.CHILD_BADGE
            if self.age_now_or_at_con < 13:
                self.ribbon = add_opt(self.ribbon_ints, c.UNDER_13)

    @presave_adjustment
    def child_ribbon_or_not(self):
        if self.age_now_or_at_con and self.age_now_or_at_con < 13:
            self.ribbon = add_opt(self.ribbon_ints, c.UNDER_13)
        elif c.UNDER_13 in self.ribbon_ints and self.age_now_or_at_con and self.age_now_or_at_con >= 13:
            self.ribbon = remove_opt(self.ribbon_ints, c.UNDER_13)

    @presave_adjustment
    def child_to_attendee(self):
        if self.badge_type == c.CHILD_BADGE and self.age_now_or_at_con and self.age_now_or_at_con >= 18:
            self.badge_type = c.ATTENDEE_BADGE
            self.ribbon = remove_opt(self.ribbon_ints, c.UNDER_13)

    @property
    def age_discount(self):
        # We dynamically calculate the age discount to be half the
        # current badge price. If for some reason the default discount
        # (if it exists) is greater than half off, we use that instead.
        import math
        if self.age_now_or_at_con and self.age_now_or_at_con < 13:
            half_off = math.ceil(c.BADGE_PRICE / 2)
            if not self.age_group_conf['discount'] or self.age_group_conf['discount'] < half_off:
                return -half_off
        return -self.age_group_conf['discount']
            
    @property
    def volunteer_event_shirt_eligible(self):
        return bool(c.VOLUNTEER_RIBBON in self.ribbon_ints and c.HOURS_FOR_SHIRT and not self.walk_on_volunteer)
            
    @property
    def staff_merch_items(self):
        """Used by the merch and staff_merch properties for staff swag."""
        merch = ["Volunteer lanyard", "Volunteer button"] if self.staffing else []
        if self.walk_on_volunteer and self.worked_hours >= 6:
            merch.append("Walk-on volunteer coffee mug")
        if not self.walk_on_volunteer and self.worked_hours >= c.HOURS_FOR_REFUND:
            merch.append("Staff Swadge")
        num_staff_shirts_owed = self.num_staff_shirts_owed
        if num_staff_shirts_owed > 0:
            staff_shirts = '{} Staff Shirt{}'.format(num_staff_shirts_owed, 's' if num_staff_shirts_owed > 1 else '')
            if self.shirt_size_marked:
                try:
                    if c.STAFF_SHIRT_OPTS != c.SHIRT_OPTS:
                        staff_shirts += ' [{}]'.format(c.STAFF_SHIRTS[self.staff_shirt])
                    else:
                        staff_shirts += ' [{}]'.format(c.SHIRTS[self.shirt])
                except KeyError:
                    staff_shirts += ' [{}]'.format("Size unknown")
            merch.append(staff_shirts)

        if self.staffing:
            merch.append('Staffer Info Packet')

        return merch

    @property
    def is_not_ready_to_checkin(self):
        """
        Returns None if we are ready for checkin, otherwise a short error
        message why we can't check them in.
        """
        
        if self.badge_status == c.WATCHED_STATUS:
            if self.banned or not self.regdesk_info:
                regdesk_info_append = " [{}]".format(self.regdesk_info) if self.regdesk_info else ""
                return "MUST TALK TO SECURITY before picking up badge{}".format(regdesk_info_append)
            return self.regdesk_info or "Badge status is {}".format(self.badge_status_label)

        if self.badge_status not in [c.COMPLETED_STATUS, c.NEW_STATUS]:
            return "Badge status is {}".format(self.badge_status_label)
        
        if self.placeholder:
            return "Placeholder badge"

        if self.is_unassigned:
            return "Badge not assigned"

        if self.is_presold_oneday:
            if self.badge_type_label != localized_now().strftime('%A'):
                return "Wrong day"

        if self.donate_badge_cost:
            return "Asked badge + merch to be shipped to them"

        message = check(self)
        return message


class SeasonPassTicket(MagModel):
    fk_id = Column(UUID)
    slug = Column(UnicodeText)

    @property
    def fk(self):
        return self.session.season_pass(self.fk_id)


class PrevSeasonSupporter(MagModel):
    first_name = Column(UnicodeText)
    last_name = Column(UnicodeText)
    email = Column(UnicodeText)

    email_model_name = 'attendee'  # used by AutomatedEmailFixture code

    _repr_attr_names = ['first_name', 'last_name', 'email']
