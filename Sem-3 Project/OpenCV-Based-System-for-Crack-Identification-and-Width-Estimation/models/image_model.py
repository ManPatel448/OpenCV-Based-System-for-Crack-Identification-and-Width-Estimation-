from .database import get_db, get_fallback_store


def create_image(document):
    db = get_db()
    if db is not None:
        db.images.insert_one(document)
    else:
        get_fallback_store()["images"].setdefault(document["analysis_id"], []).append(document.copy())
    return document


def list_images(analysis_id):
    db = get_db()
    if db is not None:
        return list(db.images.find({"analysis_id": analysis_id}).sort("uploaded_at", 1))
    return sorted(get_fallback_store()["images"].get(analysis_id, []), key=lambda item: item.get("uploaded_at"))


def update_image(image_id, values):
    db = get_db()
    if db is not None:
        db.images.update_one({"image_id": image_id}, {"$set": values})
    else:
        for images in get_fallback_store()["images"].values():
            for image in images:
                if image["image_id"] == image_id:
                    image.update(values)
