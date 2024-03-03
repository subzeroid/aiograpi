class MultipleAccountsMixin:
    """
    Helpers for multiple accounts.
    """

    async def featured_accounts_v1(self, target_user_id: str) -> dict:
        target_user_id = str(target_user_id)
        return await self.private_request(
            "multiple_accounts/get_featured_accounts/",
            params={"target_user_id": target_user_id},
        )

    async def get_account_family_v1(self) -> dict:
        return await self.private_request("multiple_accounts/get_account_family/")
