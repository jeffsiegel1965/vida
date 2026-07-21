#!/usr/bin/env python3
"""Generate an on-chain proof card and post to X.

Usage:
  python3 scripts/post_proof_card.py \
    --txid d32b4504... \
    --operation "Escrow Release" \
    --amount "10 KAS" \
    --network "Kaspa Mainnet" \
    --note "Agent-to-agent escrow settled"

Creates a 1920x1080 image card and posts it to @VidaWallet.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ── Config ──
FONT_DIR = Path("/usr/share/fonts")
OUTPUT_DIR = Path("/home/jeff-siegel/.hermes/projects/vida-release/assets/proof_cards")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Colors (dark theme)
BG = (10, 12, 14)
ACCENT = (112, 199, 186)  # teal
TEXT_WHITE = (233, 241, 239)
TEXT_MUTED = (167, 184, 180)
TEXT_ACCENT = (112, 199, 186)
CARD_W, CARD_H = 1920, 1080


def find_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Find best available sans-serif font."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(str(p), size)
    # Fallback
    return ImageFont.load_default()


def create_card(
    txid: str,
    operation: str,
    amount: str,
    network: str = "Kaspa Mainnet",
    note: str = "",
    output_path: str | Path = "",
) -> Path:
    """Create a branded transaction proof card."""

    font_big = find_font(64, bold=True)
    font_mid = find_font(42, bold=True)
    font_small = find_font(32)
    font_tiny = find_font(24)

    img = Image.new("RGB", (CARD_W, CARD_H), BG)
    draw = ImageDraw.Draw(img)

    # ── Top accent line ──
    draw.rectangle([(0, 0), (CARD_W, 6)], fill=ACCENT)

    # ── Vida branding ──
    draw.text((80, 50), "VIDA", fill=TEXT_ACCENT, font=font_big)
    draw.text((80, 120), "Agent Wallet", fill=TEXT_MUTED, font=font_small)

    # ── Status badge ──
    badge_x, badge_y = 80, 200
    badge_w, badge_h = 280, 50
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)],
        radius=25,
        fill=(20, 30, 28),
        outline=ACCENT,
    )
    draw.text((badge_x + 30, badge_y + 8), "✅ ON-CHAIN", fill=TEXT_ACCENT, font=font_small)

    # ── Operation type ──
    draw.text((80, 310), operation, fill=TEXT_WHITE, font=font_big)

    # ── Amount ──
    draw.text((80, 400), amount, fill=TEXT_ACCENT, font=font_big)

    # ── Network ──
    draw.text((80, 490), network, fill=TEXT_MUTED, font=font_small)

    # ── Txid ──
    txid_display = txid[:20] + "..." if len(txid) > 24 else txid
    draw.text((80, 570), f"Tx: {txid_display}", fill=TEXT_MUTED, font=font_tiny)

    # ── Full txid (copyable) ──
    draw.text((80, 610), f"Full: {txid}", fill=TEXT_MUTED, font=font_tiny)

    # ── Note ──
    if note:
        draw.text((80, 680), note, fill=TEXT_WHITE, font=font_mid)

    # ── Footer ──
    draw.text((80, CARD_H - 80), "VidaWallet", fill=TEXT_MUTED, font=font_tiny)
    draw.text((CARD_W - 280, CARD_H - 80), "kaspa.org", fill=TEXT_MUTED, font=font_tiny)

    # ── Separator line ──
    draw.line([(80, CARD_H - 110), (CARD_W - 80, CARD_H - 110)], fill=(30, 40, 38), width=1)

    # ── Save ──
    if not output_path:
        short = txid[:8]
        output_path = OUTPUT_DIR / f"proof_{short}.png"
    img.save(str(output_path), "PNG")
    print(f"Card saved: {output_path}")
    return Path(output_path)


def post_to_x(image_path: Path, text: str) -> bool:
    """Upload image and post to X via xurl."""
    try:
        # Upload media
        result = subprocess.run(
            ["xurl", "media", "upload", str(image_path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            print(f"Media upload failed: {result.stderr}")
            return False

        # Parse media ID from output
        media_id = result.stdout.strip()
        print(f"Uploaded media: {media_id}")

        # Post with media
        post_result = subprocess.run(
            ["xurl", "post", text, "--media", media_id],
            capture_output=True, text=True, timeout=30,
        )
        if post_result.returncode != 0:
            print(f"Post failed: {post_result.stderr}")
            return False
        print(f"Posted: {post_result.stdout.strip()}")
        return True

    except FileNotFoundError:
        print("xurl not found. Install with: npm install -g xurl")
        return False
    except Exception as e:
        print(f"Error posting: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Post an on-chain proof card to X")
    parser.add_argument("--txid", required=True, help="Transaction hash")
    parser.add_argument("--operation", required=True, help="Operation type (e.g. 'Escrow Release')")
    parser.add_argument("--amount", required=True, help="Amount (e.g. '10 KAS')")
    parser.add_argument("--network", default="Kaspa Mainnet", help="Network name")
    parser.add_argument("--note", default="", help="Optional note")
    parser.add_argument("--post", action="store_true", help="Actually post to X (dry-run without this)")
    args = parser.parse_args()

    # Create card
    card_path = create_card(
        txid=args.txid,
        operation=args.operation,
        amount=args.amount,
        network=args.network,
        note=args.note,
    )

    # Build post text (STE100)
    post_text = f"Vida | {args.operation}. {args.amount}. {args.network}."
    if args.note:
        post_text += f" {args.note}"
    if len(post_text) > 260:
        post_text = post_text[:257] + "..."

    print(f"\nPost text: {post_text}")
    print(f"Card: {card_path}")

    if args.post:
        post_to_x(card_path, post_text)
    else:
        print("\nDry-run. Pass --post to actually post to X.")
        print("Example: python3 scripts/post_proof_card.py \\")
        print("  --txid d32b4504... --operation 'Escrow Release' \\")
        print("  --amount '10 KAS' --note 'Agent-to-agent' --post")


if __name__ == "__main__":
    main()
