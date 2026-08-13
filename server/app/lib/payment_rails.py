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

3. **No amount prefill yet, and the code must not pretend otherwise.** Prefill
   needs the SELLER's handle (`paypal.me/<handle>/<amount>`,
   `venmo.com/<handle>?amount=`), and no column holds one — verified against the
   live schema 2026-08-14, where the only handle columns are display names. The
   honest interim is to open the rail and show the amount as selectable text.
   When a handle column lands, add `deep_link_template` here and NOT at the call
   sites.

Apple: physical goods shipped between members are outside IAP — spec §5,
"Must not use IAP for this — that is the rule, not a loophole."
"""

from __future__ import annotations

from typing import Optional

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
    ),
    PaymentRail(
        key="wise",
        label="Wise",
        url="https://wise.com/",
        coverage="Most countries",
        reversible=False,
        note="A transfer, not a card payment — there is no chargeback.",
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
                    coverage="EEA and UK", reversible=False),
        PaymentRail(key="swish", label="Swish", url="https://www.swish.nu/",
                    coverage="Sweden", reversible=False),
        PaymentRail(key="tikkie", label="Tikkie", url="https://www.tikkie.me/",
                    coverage="Netherlands", reversible=False,
                    note="The seller creates the request in their own bank app."),
    ],
    "americas": [
        PaymentRail(key="cashapp", label="Cash App", url="https://cash.app/",
                    coverage="United States, United Kingdom", reversible=False),
        PaymentRail(key="interac", label="Interac e-Transfer", url="https://www.interac.ca/",
                    coverage="Canada", reversible=False),
        PaymentRail(key="revolut", label="Revolut", url="https://www.revolut.com/",
                    coverage="United States and EEA", reversible=False),
        PaymentRail(key="venmo", label="Venmo", url="https://venmo.com/",
                    coverage="United States", reversible=False),
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
