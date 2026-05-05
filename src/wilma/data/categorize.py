"""
Wilma — rule-based scam categorization.

Takes cleaned messages and assigns them to fine-grained scam categories
using keyword/regex rules. Designed to recategorize the generic
'scam_other' label produced by Day-3/4 cleaners.

Rules are evaluated in priority order. The first matching rule wins.
"""

from __future__ import annotations

import re
from typing import Final


def _word_re(words):
    """Match any of the given words/phrases as whole words, case-insensitive."""
    pattern = r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b"
    return re.compile(pattern, re.IGNORECASE)


# Crypto scams
RE_CRYPTO: Final = _word_re([
    "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency",
    "binance", "coinbase", "metamask", "wallet address",
    "doubling your", "double your bitcoin", "2x your", "10x your",
    "altcoin", "shitcoin", "memecoin", "defi", "nft mint",
    "elon musk giveaway", "free crypto", "airdrop",
])

# Fake OTP
RE_FAKE_OTP: Final = re.compile(
    r"\b(?:"
    r"otp|one[- ]time[- ]password|verification[- ]code|"
    r"security[- ]code|confirm[- ]code|"
    r"do not share (?:your|this) (?:otp|code|pin)|"
    r"share (?:your|the) otp|share (?:your|the) code|"
    r"send (?:the|your) (?:otp|code|pin)"
    r")\b",
    re.IGNORECASE,
)

# Fake loan
RE_FAKE_LOAN: Final = re.compile(
    r"\b(?:"
    r"instant loan|quick loan|fast loan|easy loan|approved loan|"
    r"loan approval|loan offer|low interest loan|no collateral|"
    r"processing fee|service fee|insurance fee|"
    r"loan disburse|disbursement fee|refundable fee"
    r")\b",
    re.IGNORECASE,
)

# Romance
RE_ROMANCE: Final = re.compile(
    r"\b(?:"
    r"my dear love|my love|my darling|my sweetheart|"
    r"i (?:saw|got) your (?:photo|picture|profile|number) (?:on|from)|"
    r"i (?:am|m) looking for (?:a|my) (?:soulmate|partner|life partner|husband|wife)|"
    r"god directed me to you|destiny brought us|"
    r"widow|widower|single mother|lonely heart|"
    r"my late husband|my late wife|"
    r"will you be my friend|i need a serious relationship"
    r")\b",
    re.IGNORECASE,
)

# Impersonation brands
RE_IMPERSONATION: Final = re.compile(
    r"\b(?:"
    r"mtn|airtel|glo|9mobile|"
    r"gtbank|gtb|access bank|zenith bank|first bank|uba|fidelity bank|"
    r"opay|palmpay|moniepoint|kuda|carbon|fairmoney|"
    r"cbn|efcc|nimc|nin|bvn|"
    r"central bank|federal government|"
    r"paypal|stripe|amazon|apple support|microsoft support|"
    r"irs|hmrc"
    r")\b",
    re.IGNORECASE,
)

# Phishing triggers
RE_PHISHING_TRIGGERS: Final = re.compile(
    r"\b(?:"
    r"verify (?:your )?account|confirm (?:your )?(?:identity|details|account)|"
    r"account (?:has been )?(?:suspended|locked|frozen|blocked|deactivated|limited|restricted)|"
    r"unusual (?:sign[- ]?in|activity|login)|"
    r"click (?:here|the link|this link) to|update (?:your )?(?:account|password|details)|"
    r"reactivate (?:your )?account|secure (?:your )?account|"
    r"failed login|sign[- ]?in attempt"
    r")\b",
    re.IGNORECASE,
)
RE_LINK: Final = re.compile(r"<URL>", re.IGNORECASE)

# Advance fee 419
RE_419: Final = re.compile(
    r"\b(?:"
    r"million (?:united states |us )?dollars|usd\$\d+m|"
    r"\$\d+\s?(?:million|m\b)|"
    r"unclaimed (?:fund|funds|estate|inheritance|account|deposit)|"
    r"next of kin|business proposal|business assistance|"
    r"transfer of fund|fund transfer|dormant account|"
    r"diplomatic (?:box|consignment|courier)|"
    r"inheritance|beneficiary of|the deceased|late (?:mr|mrs|chief|dr|engr|husband|wife|father|mother|uncle|aunt)|"
    r"foreign partner|trustworthy partner|reliable foreign|"
    r"share the (?:fund|money|sum)|percentage of the (?:fund|sum|money)|"
    r"contact me (?:urgently|immediately)|strictly confidential|"
    r"chamber of commerce|bank manager|bank official"
    r")\b",
    re.IGNORECASE,
)
RE_419_GEO: Final = _word_re([
    "lagos", "abuja", "abidjan", "accra", "lome", "togo", "benin republic",
    "ivory coast", "ivoire", "burkina faso", "ouagadougou",
    "zimbabwe", "harare", "congo", "kinshasa", "drc",
])

# Commercial spam
RE_COMMERCIAL: Final = _word_re([
    "viagra", "cialis", "levitra", "pharmacy",
    "pills", "weight loss", "lose weight", "diet pill",
    "rolex", "replica", "casino", "online casino", "poker",
    "sex", "porn", "xxx", "adult", "singles in your area",
    "make money fast", "work from home", "earn $", "make $",
])

# Prize indicator
RE_PRIZE: Final = re.compile(
    r"\b(?:"
    r"you (?:have )?won|congratulations[!,. ]+you|"
    r"winner of|lucky winner|"
    r"selected (?:as|to be) (?:a |the )?winner|"
    r"claim (?:your |the )?prize|prize winner"
    r")\b",
    re.IGNORECASE,
)


# Order matters! First match wins. Most specific first.
CATEGORY_PRIORITY: Final = [
    "fake_otp",
    "fake_loan",
    "crypto_scam",
    "advance_fee_419",
    "romance",
    "phishing",
    "impersonation",
    "commercial_spam",
]


def _matches(text):
    has_url = bool(RE_LINK.search(text))
    return {
        "fake_otp": bool(RE_FAKE_OTP.search(text)),
        "fake_loan": bool(RE_FAKE_LOAN.search(text)),
        "crypto_scam": bool(RE_CRYPTO.search(text)),
        "romance": bool(RE_ROMANCE.search(text)),
        "advance_fee_419": bool(RE_419.search(text) or RE_419_GEO.search(text)),
        "phishing": bool(RE_PHISHING_TRIGGERS.search(text) and has_url),
        "impersonation": bool(
            RE_IMPERSONATION.search(text)
            and (RE_PHISHING_TRIGGERS.search(text) or RE_PRIZE.search(text))
        ),
        "commercial_spam": bool(RE_COMMERCIAL.search(text)),
    }


def categorize_message(text, original_category):
    """Return the best fine-grained category for a message."""
    if original_category == "legitimate":
        return "legitimate"
    if original_category == "advance_fee_419":
        return "advance_fee_419"

    text = str(text)
    matches = _matches(text)
    for cat in CATEGORY_PRIORITY:
        if matches[cat]:
            return cat
    return "scam_other"
