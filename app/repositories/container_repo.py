from sqlalchemy.orm import Session
from app.models import Container, ParameterVersion
from typing import Optional


def get_all_containers(db: Session) -> list:
    return db.query(Container).order_by(Container.created_at.desc()).all()


def get_container_by_id(db: Session, container_id: int) -> Optional[Container]:
    return db.query(Container).filter(Container.id == container_id).first()


def create_container(db: Session, **kwargs) -> Container:
    container = Container(**kwargs)
    db.add(container)
    db.commit()
    db.refresh(container)
    return container


def update_container(db: Session, container: Container, **kwargs) -> Container:
    for key, value in kwargs.items():
        setattr(container, key, value)
    db.commit()
    return container


def delete_container(db: Session, container: Container) -> None:
    db.delete(container)
    db.commit()


def count_parameter_versions(db: Session, container_id: int) -> int:
    return db.query(ParameterVersion).filter(
        ParameterVersion.container_id == container_id
    ).count()
