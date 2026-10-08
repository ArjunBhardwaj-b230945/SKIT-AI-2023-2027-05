# ============================================================
# Password Update
# ============================================================

def update_user_password(
    user_id: int,
    current_password: str,
    new_password: str
):
    """
    Change the password of an existing user.

    The current password must be verified before the new
    password is stored.
    """

    user = find_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is required"
        )

    if not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password is required"
        )

    if not verify_password(
        current_password,
        user["password"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )

    validate_password(new_password)

    if verify_password(
        new_password,
        user["password"]
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )

    user["password"] = hash_password(new_password)

    return {
        "success": True,
        "message": "Password updated successfully"
    }