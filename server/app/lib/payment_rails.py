"""Payment rails a member can settle up on, by region.

Sparrow NEVER touches the money. This module is a directory: it names rails,
says whether each is reversible, and links to the rail's own site. The two
members transact there, under their own accounts, with their own PSP.

Read docs/P2P_MARKETPLACE_SPEC.md §5a before changing anything here. The line
that governs this file:

    We may                                  We may not
    ------------------------------------    ----------------------------------
    Deep-link out with the amount            Hold funds, even momentarily.
    prefilled — a hyperlink is not           There is no de-minimis
    payment initiation under PSD2
    Art. 4(15); the user's own PSP
    initiates the order

    Compare payment rails NEUTRALLY          Say "we recommend X" — that is a
    (reversible vs not)                      representation

    Record a payment CLAIM the seller        Issue a receipt in Sparrow's name
    asserts

    Point at the payment rail's own          Mediate, or offer any refund or
    dispute process                          guarantee

Three consequences for the code below:

1. **Order is alphabetical, and that is load-bearing.** A "recommended" rail, a
   pinned first entry, or an order derived from anything we prefer is a
   representation about a payment provider. Alphabetical is defensible and
   visibly arbitrary. `rails_for_region` sorts; do not hand-order the lists.

2. **`reversible` is the one comparison we are allowed to make**, and §5a names
   it explicitly. It is the single most useful safety fact for a member: a
   bank transfer or a Friends-and-Family send has no chargeback, and a member
   who does not know that learns it by losing money.

3. **Amount prefill is per-rail and opt-in.** `deep_link_template` is set only
   for rails with a documented public link format that carries the amount. A
   rail without one is not broken — the buyer opens it and types the figure,
   which is what everyone did before. The seller's handle comes from
   `user_payment_handles` (migration 20260814) and is only ever resolved for the
   COUNTERPARTY of an accepted trade, server-side; the table itself is
   owner-only under RLS.

Apple: physical goods shipped between members are outside IAP — spec §5,
"Must not use IAP for this — that is the rule, not a loophole."
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import quote_plus

from pydantic import BaseModel

# Regions mirror `Region` in src/lib/settings.tsx exactly:
# americas | europe | japan | korea | oceania | other.
# A rail listed under a region is one a member THERE can plausibly use; it is
# not a claim about availability in every country of that region, which is why
# `coverage` is shown to the user rather than being hidden as a filter.
REGIONS = ("americas", "europe", "japan", "korea", "oceania", "other")


class PaymentRail(BaseModel):
    key: str
    label: str
    url: str
    coverage: str
    #: True  = the payer has a formal chargeback/protection route.
    #: False = once sent, it is gone.
    #: None  = depends how it is sent (PayPal is the case this exists for).
    reversible: Optional[bool] = None
    #: Shown verbatim next to the rail. Facts only — never advice.
    note: Optional[str] = None
    #: What to ask the SELLER for, e.g. "PayPal.Me name". None = this rail has
    #: no public identifier we can build a link from, so no handle is collected.
    handle_label: Optional[str] = None
    #: `{handle}`, `{amount}`, `{currency}` are substituted server-side. Present
    #: only where the rail documents a public URL that carries an amount —
    #: guessing a format produces a link that 404s at the worst moment.
    deep_link_template: Optional[str] = None


# Global rails, offered everywhere. Kept separate so a region list stays short
# and a rail cannot drift between the two.
_GLOBAL: list[PaymentRail] = [
    PaymentRail(
        key="paypal",
        label="PayPal",
        url="https://www.paypal.com/",
        coverage="Most countries",
        # The ONE rail where reversibility depends on how the payer sends.
        # Goods & Services carries buyer protection; Friends & Family does not
        # and is the standard way people get burned on a marketplace.
        reversible=None,
        note="Goods & Services is covered by PayPal's buyer protection. Friends & Family is not.",
        handle_label="PayPal.Me name",
        # DOCUMENTED: paypal.me/<user>/<amount><CUR> — PayPal's own help gives
        # "PayPal.Me/DiaRusso/25AUD". The short domain is the canonical one.
        deep_link_template="https://paypal.me/{handle}/{amount}{currency}",
    ),
    PaymentRail(
        key="wise",
        label="Wise",
        url="https://wise.com/",
        coverage="Most countries",
        reversible=False,
        note="A transfer, not a card payment — there is no chargeback.",
        handle_label="Wise link name",
        # Wise's public pay-me link carries no amount, so the buyer still types
        # it. Listed anyway: landing on the right person is most of the value.
        deep_link_template="https://wise.com/pay/me/{handle}",
    ),
]

_BY_REGION: dict[str, list[PaymentRail]] = {
    "europe": [
        PaymentRail(key="sepa", label="Bank transfer (SEPA)", url="https://www.europeanpaymentscouncil.eu/",
                    coverage="Euro area", reversible=False,
                    note="No chargeback once it settles."),
        PaymentRail(key="bizum", label="Bizum", url="https://bizum.es/",
                    coverage="Spain", reversible=False),
        PaymentRail(key="revolut", label="Revolut", url="https://www.revolut.com/",
                    coverage="EEA and UK", reversible=False,
                    handle_label="Revolut tag (without @)",
                    # revolut.me/<tag> is documented; an amount-carrying form is
                    # NOT. Revolut generates payment links inside the app, so a
                    # URL pattern is ours to guess — and this module's rule is
                    # that a guessed format 404s at the worst moment. Lands on
                    # the right person; the buyer types the figure.
                    deep_link_template="https://revolut.me/{handle}"),
        PaymentRail(key="swish", label="Swish", url="https://www.swish.nu/",
                    coverage="Sweden", reversible=False),
        PaymentRail(key="tikkie", label="Tikkie", url="https://www.tikkie.me/",
                    coverage="Netherlands", reversible=False,
                    note="The seller creates the request in their own bank app."),
    ],
    "americas": [
        PaymentRail(key="cashapp", label="Cash App", url="https://cash.app/",
                    coverage="United States, United Kingdom", reversible=False,
                    handle_label="$Cashtag (without $)",
                    # cash.app/$<cashtag> is documented; the amount-in-path form
                    # is not. Cash App generates request links in-app.
                    deep_link_template="https://cash.app/${handle}"),
        PaymentRail(key="interac", label="Interac e-Transfer", url="https://www.interac.ca/",
                    coverage="Canada", reversible=False),
        PaymentRail(key="revolut", label="Revolut", url="https://www.revolut.com/",
                    coverage="United States and EEA", reversible=False,
                    handle_label="Revolut tag (without @)",
                    # See the europe entry: no documented amount-carrying form.
                    deep_link_template="https://revolut.me/{handle}"),
        PaymentRail(key="venmo", label="Venmo", url="https://venmo.com/",
                    coverage="United States", reversible=False,
                    handle_label="Venmo username (without @)",
                    # DOCUMENTED: txn=pay, amount, note, audience.
                    #
                    # `audience=private` is NOT decoration. Venmo posts payments
                    # to a social feed and defaults to public — without this,
                    # buying a collectible broadcasts to the payer's followers
                    # that they bought it, and from whom. A marketplace has no
                    # business making that public by omission.
                    deep_link_template=(
                        "https://venmo.com/{handle}"
                        "?txn=pay&amount={amount}&audience=private&note={note}"
                    )),
        PaymentRail(key="zelle", label="Zelle", url="https://www.zellepay.com/",
                    coverage="United States", reversible=False,
                    note="Bank-to-bank. Treated as cash — there is no dispute route."),
    ],
    "oceania": [
        PaymentRail(key="payid", label="PayID / Osko", url="https://payid.com.au/",
                    coverage="Australia", reversible=False),
    ],
    "japan": [
        PaymentRail(key="jp_bank", label="Bank transfer (furikomi)", url="https://www.zenginkyo.or.jp/en/",
                    coverage="Japan", reversible=False),
    ],
    "korea": [
        PaymentRail(key="kr_bank", label="Bank transfer", url="https://www.kftc.or.kr/eng/",
                    coverage="South Korea", reversible=False),
    ],
    "other": [],
}


def rails_for_region(region: Optional[str]) -> list[PaymentRail]:
    """Rails for a region, alphabetical by label.

    Alphabetical is not a styling choice — see the module docstring. Any other
    order is a statement about which rail we prefer, and we are not allowed to
    make one.

    An unknown or missing region falls back to the global rails rather than
    guessing: showing a Dutch member Zelle is worse than showing them less.
    """
    key = (region or "").strip().lower()
    regional = _BY_REGION.get(key, [])
    return sorted([*_GLOBAL, *regional], key=lambda r: r.label.casefold())


#: Shown with every list, in the UI, every time. Not a tooltip and not a
#: one-off onboarding note: it is the statement that keeps this a directory
#: rather than a payment service.
DISCLAIMER = (
    "Sparrow does not process, hold or verify payments. You pay the seller "
    "directly through your own provider, and any dispute is handled by that "
    "provider, not by Sparrow."
)


#: A handle goes straight into a URL path, so it is bounded to characters that
#: cannot change what the URL MEANS. `merle/../../evil` or a handle carrying
#: `?`/`#` would retarget the link the buyer taps — and the buyer taps it
#: believing Sparrow built it. Letters, digits, dot, dash and underscore cover
#: every format the rails above document.
_HANDLE_OK = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789.-_"
)


def clean_handle(raw: Optional[str]) -> Optional[str]:
    """Normalise a member-supplied handle, or None if it cannot be trusted.

    Rejects rather than strips: a handle that contained a slash is not a handle
    with a typo, it is someone trying to build a different URL, and silently
    repairing it would hide that.
    """
    if raw is None:
        return None
    h = raw.strip().lstrip("@$")
    if not (2 <= len(h) <= 64):
        return None
    if any(c not in _HANDLE_OK for c in h):
        return None
    return h


#: Currencies with no minor unit. Formatting JPY 1000 as "1000.00" is not a
#: cosmetic slip — it is a different number to a payment provider that parses
#: the path, and the two we support are exactly the two the app offers.
_ZERO_DECIMAL = {"JPY", "KRW"}


def format_amount(amount: float, currency: str) -> str:
    """Amount as the rail expects to read it."""
    return f"{amount:.0f}" if (currency or "").upper() in _ZERO_DECIMAL else f"{amount:.2f}"


def build_deep_link(
    rail: PaymentRail,
    handle: Optional[str],
    amount: float,
    currency: str,
    *,
    note: str = "",
) -> Optional[str]:
    """The rail's own URL with the amount already in it, or None.

    None means "we could not build one" — no template, no handle, or a handle
    that failed `clean_handle`. Callers must fall back to `rail.url`, never to a
    half-substituted string: a link containing a literal `{handle}` is worse
    than no link, because it looks tappable.

    Amount uses the currency's own precision — JPY and KRW have no minor unit,
    and "1000.00" is a different number to a provider parsing the path.

    `note` is URL-escaped and only reaches rails whose template asks for it
    (Venmo). It carries a trade reference so the seller can tell which of three
    outstanding trades a payment settles.
    """
    if not rail.deep_link_template:
        return None
    clean = clean_handle(handle)
    if not clean:
        return None
    if amount <= 0:
        return None
    return rail.deep_link_template.format(
        handle=clean,
        amount=format_amount(amount, currency),
        currency=(currency or "EUR").upper(),
        # quote_plus, not quote: this lands in a QUERY string, where a space
        # must be "+" or "%20" and never a raw space.
        note=quote_plus(note or ""),
    )


def carries_amount(rail: PaymentRail) -> bool:
    """Does this rail's link actually contain the figure?

    The client says "amount filled in" next to a rail, and that must not be
    said of `revolut.me/<tag>` or `cash.app/$<tag>`, which land on the right
    person and nothing more. Neither publishes an amount-carrying URL format,
    and inventing one is how a buyer taps a link that 404s.
    """
    return bool(rail.deep_link_template and "{amount}" in rail.deep_link_template)
