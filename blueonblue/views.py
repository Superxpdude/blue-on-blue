import discord

from typing import Optional

# Subclassed buttons
class ConfirmButton(discord.ui.Button):
	"""Button to confirm an action"""
	def __init__(self, *, label: Optional[str]="Confirm", style: Optional[discord.ButtonStyle]=discord.ButtonStyle.success):
		super().__init__(label = label, style = style)

	async def callback(self, interaction: discord.Interaction):
		"""Callback function for the button"""
		view: AuthorResponseViewBase = self.view
		view.response = True
		await view.terminate()

class CancelButton(discord.ui.Button):
	"""Button to cancel an action"""
	def __init__(self, *, label: Optional[str]="Confirm", style: Optional[discord.ButtonStyle]=discord.ButtonStyle.success):
		super().__init__(label = label, style = style)

	async def callback(self, interaction: discord.Interaction):
		"""Callback function for the button"""
		view: AuthorResponseViewBase = self.view
		view.response = False
		await view.terminate()

# Base view class for
class AuthorResponseViewBase(discord.ui.View):
	"""Base view class for a view that will only respond to the original user who invoked the view."""
	def __init__(self, author: discord.User|discord.Member, *, timeout: Optional[float]=120.0):
		self.response = None
		self.message: discord.InteractionMessage = None
		self.author = author
		super().__init__(timeout=timeout)

	async def terminate(self, *, timedOut: Optional[bool]=False) -> None:
		"""Overwritten "stop" function.
		Automatically deactivates all child items when the view is stopped."""
		# Disable all existing child items
		for child in self.children:
			child.disabled = True
		# Check if our view was timed out
		if timedOut:
			# Edit our message to add "Timed Out" at the end
			messageText = self.message.content # Get message text
			messageText += "\nTimed out"
			await self.message.edit(messageText, view = self)
		else:
			# We don't need to edit the message
			await self.message.edit(view = self)
		# Actually stop the view
		super().stop()

	# Only allow the original command user to interact with the buttons
	async def interaction_check(self, interaction: discord.Interaction) -> bool:
		if interaction.user == self.author:
			return True
		else:
			await interaction.response.send_message("This button is not for you.", ephemeral=True)
			return False

	async def on_timeout(self):
		await self.terminate(timedOut = True) # Stop the view, and deactivate all buttons on timeout

# Confirmation view
class ConfirmView(AuthorResponseViewBase):
	"""Confirmation dialog
	Creates a view with "Confirm" and "Cancel" buttons.
	Requires a command context to be passed through on initialization.
	Returns True for "Confirm", False for "Cancel"."""
	def __init__(self, *, timeout: Optional[float]=120.0, confirm: Optional[str]="Confirm", cancel: Optional[str]="Cancel"):
		super().__init__(timeout)
		self.add_item(ConfirmButton())
		self.add_item(CancelButton())

# Confirmation view for delete actions
class ConfirmDelete(AuthorResponseViewBase):
	"""Delete confirmation dialog
	Same setup as blueonblue.views.ConfirmView, but with different button labels and colours"""
	@discord.ui.button(label = "Delete", style = discord.ButtonStyle.danger)
	async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
		"""Red button for deletion"""
		self.value = True
		self.stop()

	@discord.ui.button(label = "Cancel", style = discord.ButtonStyle.secondary)
	async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
		"""Grey button for cancellation"""
		self.value = False
		self.stop()
