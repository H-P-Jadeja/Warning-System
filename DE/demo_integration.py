"""Exercise committed CRUD through app.db with a disposable recipient."""

from app import db


def demo():
    if db.backend_name() != "PostgreSQL":
        raise SystemExit("Set DATABASE_URL and run python -m DE.setup_db.")
    print("Backend:", db.backend_name())
    recipient_id = db.add_recipient("Illustrative CRUD demo", "Observer", is_active=False)
    try:
        print("After INSERT and SELECT:")
        print(db.get_recipients().query("recipient_id == @recipient_id").to_string(index=False))
        assert db.update_recipient(recipient_id, "Illustrative CRUD demo", "Coordinator", is_active=False)
        print("After UPDATE and SELECT:")
        print(db.get_recipients().query("recipient_id == @recipient_id").to_string(index=False))
    finally:
        assert db.delete_recipient(recipient_id)
    remaining = db.get_recipients().query("recipient_id == @recipient_id")
    print("After DELETE and SELECT, matching rows:", len(remaining))
    assert remaining.empty


if __name__ == "__main__":
    demo()
