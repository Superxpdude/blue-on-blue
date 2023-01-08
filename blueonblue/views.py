import discord

import logging
_log = logging.getLogger(__name__)

# Base view class for a view that only responds to the author
class AuthorResponseViewBase(discord.ui.View):
	"""Base view class for a view that will only respond to the original user who invoked the view."""
	def __init__(self, author: discord.User|discord.Member, *args, timeout: float=120.0, **kwargs):
		self.response: bool | None = None
		self.message: discord.InteractionMessage | None = None
		self.author = author
		super().__init__(*args, timeout=timeout, **kwargs)

	async def terminate(self, *, timedOut: bool | None = False) -> None:
		"""Overwritten "stop" function.
		Automatically deactivates all child items when the view is stopped."""
		# Disable all existing child items
		for child in self.children:
			assert isinstance(child, (discord.ui.Button, discord.ui.Select))
			child.disabled = True
		# Only try to edit the original message if we *have* the original message
		if self.message is not None:
			# Check if our view was timed out
			if timedOut:
				# Edit our message to add "Timed Out" at the end
				messageText = self.message.content # Get message text
				messageText += "\nTimed out"
				await self.message.edit(content = messageText, view = self)
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

# Subclassed buttons
class ConfirmButton(discord.ui.Button):
	"""Button to confirm an action"""
	view: AuthorResponseViewBase
	def __init__(self, *args, label: str="Confirm", style: discord.ButtonStyle=discord.ButtonStyle.success, **kwargs):
		super().__init__(*args, label = label, style = style, **kwargs)

	async def callback(self, interaction: discord.Interaction):
		"""Callback function for the button"""
		self.view.response = True
		await self.view.terminate()
		await interaction.response.defer()

class ConfirmButtonRed(ConfirmButton):
	"""Button to confirm an action. Red for destructive actions"""
	def __init__(self, *args, label: str="Confirm", style: discord.ButtonStyle=discord.ButtonStyle.danger, **kwargs):
		super().__init__(*args, label = label, style = style, **kwargs)

class CancelButton(discord.ui.Button):
	"""Button to cancel an action"""
	view: AuthorResponseViewBase
	def __init__(self, *args, label: str="Cancel", style: discord.ButtonStyle=discord.ButtonStyle.secondary, **kwargs):
		super().__init__(*args, label = label, style = style, **kwargs)

	async def callback(self, interaction: discord.Interaction):
		"""Callback function for the button"""
		self.view.response = False
		await self.view.terminate()
		await interaction.response.defer()

# Confirmation view
class ConfirmView(AuthorResponseViewBase):
	"""Confirmation dialog
	Creates a view with "Confirm" and "Cancel" buttons.
	Requires a command context to be passed through on initialization.
	Returns True for "Confirm", False for "Cancel"."""
	def __init__(self, *args, confirm: str="Confirm", cancel: str="Cancel", **kwargs):
		super().__init__(*args, **kwargs)
		self.add_item(ConfirmButton(label = confirm))
		self.add_item(CancelButton(label = cancel))

# Confirmation view for dangerous actions
class ConfirmViewDanger(AuthorResponseViewBase):
	""""Danger" confirmation dialog
	Same setup as blueonblue.views.ConfirmView, but with different button labels and colours"""
	def __init__(self, *args, confirm: str="Confirm", cancel: str="Cancel", **kwargs):
		super().__init__(*args, **kwargs)
		self.add_item(ConfirmButtonRed(label = confirm))
		self.add_item(CancelButton(label = cancel))
