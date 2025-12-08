import discord
from discord.ext import commands, tasks
import logging
from db.actions import get_active_users, get_active_role_id, set_active_role_id


async def get_or_create_active_role(guild: discord.Guild) -> discord.Role | None:
    """Get the active journaling role for a guild, creating it if it doesn't exist.
    Returns None if unable to get or create the role."""
    role_id = await get_active_role_id(guild.id)
    role = None

    if role_id:
        role = guild.get_role(role_id)

    if not role:
        # Role doesn't exist - create it
        try:
            role = await guild.create_role(
                name="Active Journaling",
                color=discord.Color.green(),
                hoist=True,
                reason="Created by bot for active journaling members"
            )
            await set_active_role_id(guild.id, role.id, guild.name)
            logging.info(f"Created Active Journaling role in guild {guild.id}")
        except discord.Forbidden:
            logging.error(f"Missing permissions to create role in guild {guild.id}")
            return None
        except discord.HTTPException as e:
            logging.error(f"Failed to create role in guild {guild.id}: {str(e)}")
            return None

    return role


class RoleManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_active_roles.start()

    def cog_unload(self):
        self.update_active_roles.cancel()

    @tasks.loop(hours=1)
    async def update_active_roles(self):
        """Periodically check and update active journaling roles for all guilds."""
        for guild in self.bot.guilds:
            try:
                await self._update_guild_active_roles(guild)
            except Exception as e:
                logging.error(f"Error updating active roles for guild {guild.id}: {str(e)}")

    @update_active_roles.before_loop
    async def before_update_active_roles(self):
        """Wait until the bot is ready before starting the loop."""
        await self.bot.wait_until_ready()

    async def _update_guild_active_roles(self, guild: discord.Guild):
        """Update active roles for a specific guild."""
        # Get or create the active role
        role = await get_or_create_active_role(guild)
        if not role:
            return

        # Get list of active users (journaled in last 3 days)
        active_user_ids = await get_active_users(guild.id, days=3)
        active_user_ids_set = set(active_user_ids)

        # Update roles for all members
        for member in guild.members:
            if member.bot:
                continue

            should_have_role = member.id in active_user_ids_set
            has_role = role in member.roles

            try:
                if should_have_role and not has_role:
                    # Add role
                    await member.add_roles(role, reason="Active journaling in last 3 days")
                elif not should_have_role and has_role:
                    # Remove role
                    await member.remove_roles(role, reason="No journaling in last 3 days")
            except discord.Forbidden:
                logging.error(f"Missing permissions to manage roles for user {member.id} in guild {guild.id}")
            except discord.HTTPException as e:
                logging.error(f"Failed to update role for user {member.id} in guild {guild.id}: {str(e)}")

    roles = discord.SlashCommandGroup("roles", "Role management")

    @roles.command(description="[Admin] Manually trigger active role check")
    @discord.default_permissions(administrator=True)
    async def check_active(self, ctx: discord.ApplicationContext):
        guild = ctx.guild
        if not guild:
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        try:
            await self._update_guild_active_roles(guild)
            await ctx.followup.send("Active roles updated successfully!", ephemeral=True)
        except Exception as e:
            logging.error(f"Error manually updating active roles for guild {guild.id}: {str(e)}")
            await ctx.followup.send("An error occurred while updating roles.", ephemeral=True)

    @roles.command(description="[Admin] Set which role to use for active journaling")
    @discord.default_permissions(administrator=True)
    @discord.option("role", description="The role to assign to active journalers")
    async def set_active_role(self, ctx: discord.ApplicationContext, role: discord.Role):
        guild = ctx.guild
        if not guild:
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return

        try:
            await set_active_role_id(guild.id, role.id, guild.name)
            await ctx.respond(f"Active journaling role set to {role.mention}", ephemeral=True)
        except Exception as e:
            logging.error(f"Error setting active role for guild {guild.id}: {str(e)}")
            await ctx.respond("An error occurred while setting the role.", ephemeral=True)


def setup(bot):
    bot.add_cog(RoleManagement(bot))
