"""
Entry point – Smart Monitoring & Inspection App (SIH26095)

Basic run:
    python run.py

With HTTPS (required for camera / GPS on mobile):
    python run.py --ssl
"""
import argparse
from app import create_app

app = create_app()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Monitoring App")
    parser.add_argument(
        "--ssl",
        action="store_true",
        help="Enable adhoc HTTPS (needed for getUserMedia / Geolocation on mobile)",
    )
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on")
    args = parser.parse_args()

    ssl_context = "adhoc" if args.ssl else None
    app.run(
        host="0.0.0.0",
        port=args.port,
        debug=True,
        ssl_context=ssl_context,
        use_reloader=not args.ssl,  # reloader conflicts with adhoc SSL in some envs
    )
