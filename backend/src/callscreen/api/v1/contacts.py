"""Contact (whitelist/blocklist) management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.db.session import get_db
from callscreen.models.contact import Contact
from callscreen.schemas.contact import ContactCreate, ContactResponse, ContactUpdate
from callscreen.security.auth import get_current_user
from callscreen.utils.phone import normalize_e164

router = APIRouter()


@router.get("", response_model=list[ContactResponse])
async def list_contacts(
    contact_type: str | None = Query(None, pattern="^(whitelist|blocklist|known)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List contacts, optionally filtered by type."""
    query = select(Contact).where(Contact.user_id == current_user.id)
    if contact_type:
        query = query.where(Contact.contact_type == contact_type)
    query = query.order_by(Contact.name)
    result = await db.execute(query)
    return [ContactResponse.model_validate(c) for c in result.scalars().all()]


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    data: ContactCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Add a contact to whitelist or blocklist."""
    phone = normalize_e164(data.phone_number)

    existing = await db.execute(
        select(Contact).where(
            Contact.user_id == current_user.id,
            Contact.phone_number == phone,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Contact already exists")

    contact = Contact(
        user_id=current_user.id,
        phone_number=phone,
        name=data.name,
        contact_type=data.contact_type,
        category=data.category or "other",
        notes=data.notes or "",
    )
    db.add(contact)
    await db.flush()
    await db.refresh(contact)
    return ContactResponse.model_validate(contact)


@router.put("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: str,
    data: ContactUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update a contact."""
    result = await db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == current_user.id)
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "phone_number" and value:
            value = normalize_e164(value)
        setattr(contact, field, value)

    await db.flush()
    await db.refresh(contact)
    return ContactResponse.model_validate(contact)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Remove a contact."""
    result = await db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == current_user.id)
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    await db.delete(contact)
