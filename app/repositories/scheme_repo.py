from sqlalchemy.orm import Session
from app.models import ScaleScheme, ScaleMark
from typing import Optional


def get_schemes_by_container(db: Session, container_id: int) -> list:
    return db.query(ScaleScheme).filter(ScaleScheme.container_id == container_id).all()


def get_scheme_by_id(db: Session, scheme_id: int) -> Optional[ScaleScheme]:
    return db.query(ScaleScheme).filter(ScaleScheme.id == scheme_id).first()


def create_scheme(db: Session, **kwargs) -> ScaleScheme:
    scheme = ScaleScheme(**kwargs)
    db.add(scheme)
    db.flush()
    return scheme


def create_scale_mark(db: Session, scheme_id: int, **mark_kwargs) -> ScaleMark:
    mark = ScaleMark(scheme_id=scheme_id, **mark_kwargs)
    db.add(mark)
    return mark


def delete_scheme(db: Session, scheme: ScaleScheme) -> None:
    db.delete(scheme)
    db.commit()


def delete_scheme_marks(db: Session, scheme: ScaleScheme) -> None:
    for mark in scheme.scale_marks:
        db.delete(mark)
    db.flush()


def mark_schemes_need_review(db: Session, container_id: int) -> None:
    schemes = db.query(ScaleScheme).filter(ScaleScheme.container_id == container_id).all()
    for scheme in schemes:
        scheme.needs_review = True
