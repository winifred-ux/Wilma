"""Tests for src/wilma/data/categorize.py."""

from wilma.data.categorize import categorize_message


# Each tuple: (text, original_category, expected_category, why)
CASES = [
    # --- Don't change non-scam labels ---
    ("Hi mum, can you pick up bread on your way home", "legitimate", "legitimate",
     "legitimate stays legitimate"),
    ("URGENT BUSINESS ASSISTANCE FROM MR JAMES NGOLA", "advance_fee_419", "advance_fee_419",
     "trusted Kaggle 419 label is preserved"),

    # --- 419 patterns ---
    ("I am the next of kin of late Mr. John from Lagos with unclaimed funds", "scam_other",
     "advance_fee_419",
     "next-of-kin + unclaimed + Lagos = 419"),
    ("Please contact me urgently regarding the transfer of fund USD 25 million", "scam_other",
     "advance_fee_419",
     "transfer of fund + USD millions = 419"),
    ("Diplomatic consignment in Abidjan needs your assistance", "scam_other",
     "advance_fee_419",
     "diplomatic consignment in West African geo = 419"),

    # --- Fake OTP ---
    ("Your verification code is 123456. Do not share this OTP with anyone.", "scam_other",
     "fake_otp",
     "OTP keywords"),
    ("Please send me the OTP that was just sent to your phone", "scam_other",
     "fake_otp",
     "send OTP request = OTP scam"),

    # --- Fake loan ---
    ("Get instant loan of N500,000 with no collateral. Pay processing fee of N2500.", "scam_other",
     "fake_loan",
     "instant loan + processing fee = fake loan"),
    ("Your loan has been approved. Pay disbursement fee to receive funds.", "scam_other",
     "fake_loan",
     "loan approval + disbursement fee"),

    # --- Crypto ---
    ("Elon Musk giveaway! Send 1 BTC to this wallet address and receive 2 back.", "scam_other",
     "crypto_scam",
     "crypto giveaway scam"),
    ("Free airdrop of new memecoin, claim your wallet address now", "scam_other",
     "crypto_scam",
     "airdrop scam"),

    # --- Romance ---
    ("My dear love, I saw your photo on Instagram and want to know you better", "scam_other",
     "romance",
     "romance opener"),
    ("I am a widow looking for a serious relationship, my late husband left me funds", "scam_other",
     "advance_fee_419",
     "widow + late husband + funds is 419 (priority over romance)"),

    # --- Phishing ---
    ("Your account has been suspended. Click here to verify: <URL>", "scam_other",
     "phishing",
     "account suspended + URL = phishing"),
    ("Unusual sign-in attempt detected. Confirm your identity at <URL>", "scam_other",
     "phishing",
     "unusual sign-in + URL"),

    # --- Impersonation (requires brand + trigger) ---
    ("MTN Promo: You have won N5,000,000! Send CLAIM to 32232", "scam_other",
     "impersonation",
     "MTN brand + prize trigger"),
    ("GTBank: Your account has been suspended. Verify now at <URL>", "scam_other",
     "phishing",
     "phishing wins over impersonation when URL is present"),

    # --- Commercial spam ---
    ("Cheap Viagra and Cialis, no prescription needed, save 70%", "scam_other",
     "commercial_spam",
     "Viagra/Cialis = commercial spam"),
    ("Authentic Rolex replica watches at low prices", "scam_other",
     "commercial_spam",
     "Rolex replica"),

    # --- Fallback ---
    ("Hello, how are you doing today friend", "scam_other",
     "scam_other",
     "no category triggers, stays scam_other"),
]


def test_categorize_all_cases() -> None:
    """Run every case and report all failures together."""
    failures = []
    for text, original, expected, why in CASES:
        actual = categorize_message(text, original)
        if actual != expected:
            failures.append(
                f"\n  FAIL: expected={expected!r:25s} got={actual!r:25s} | {why}\n"
                f"        text: {text[:80]}"
            )
    assert not failures, "Categorizer failures:" + "".join(failures)
