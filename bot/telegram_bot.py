import logging
import re
from telegram import (
    KeyboardButton,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ForceReply,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)
from config import SHEETS_READ_URL
from models.google_services import GoogleServices, GoogleDrive
from models.telegram_user import TelegramUser
from models.notification import NotificationSender

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class TelegramBot:
    """
    A class to handle Telegram bot interactions and manage data operations.

    Attributes:
        token (str): The bot token for authentication with the Telegram API.
        current_card_id (dict, optional): The current card ID being managed. Defaults to None.
        field_to_update (str, optional): The field to update. Defaults to None.
        application (Application): The application instance for handling Telegram updates.
    """

    def __init__(self, token: str) -> None:
        """
        Initializes the TelegramBot instance with the provided bot token.

        Args:
            token (str): The bot token for authentication with the Telegram API.
        """
        logger.info("Initializing TelegramBot instance")
        self.token = token
        self.current_card_id = None
        self.field_to_update = None
        self.application = ApplicationBuilder().token(token).build()

    def validate_name(self, name: str) -> bool:
        """
        Validates the company name.

        Args:
            name (str): The company name to validate.

        Returns:
            bool: True if the name is valid, False otherwise.
        """
        return bool(re.match(r"^[a-zA-Zа-яА-Я\s\']+$", name))

    def validate_type(self, type: str) -> bool:
        """
        Validates the company type.

        Args:
            type (str): The company type to validate.

        Returns:
            bool: True if the type is valid, False otherwise.
        """
        valid_types = ["Places to eat", "Adventures", "Services"]
        return type in valid_types

    def validate_photos(self, photos: list) -> bool:
        """
        Validates the company photos.

        Args:
            photos (list[PhotoSize]): The list of photos to validate.

        Returns:
            bool: True if the photos are valid, False otherwise.
        """
        return isinstance(photos, list) and all(
            hasattr(photo, "file_id") for photo in photos
        )

    def validate_google_maps(self, url: str) -> bool:
        """
        Validates the Google Maps URL.

        Args:
            url (str): The Google Maps URL to validate.

        Returns:
            bool: True if the URL is valid, False otherwise.
        """
        return bool(re.match(r"^https:\/\/maps\.app\.goo\.gl\/[a-zA-Z0-9]+$", url))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handles the start command to authenticate the user and provide options for adding a new organization.

        Args:
            update (Update): The update object containing the incoming update.
            context (ContextTypes.DEFAULT_TYPE): The context from the update.
        """
        logger.info("Handling start command")
        user_id = update.message.from_user.id
        user = TelegramUser.auth(user_id)

        if user:
            logger.info(f"Authenticated user ID: {user_id}, Role: {user.role}")

            button_begin = InlineKeyboardButton(
                text="Show place card", callback_data="button_add_pressed"
            )

            show_unfilled_button = InlineKeyboardButton(
                text="Show unfilled places", callback_data="show_unfilled_places"
            )

            keyboard = InlineKeyboardMarkup([[button_begin], [show_unfilled_button]])

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Hi! Choose an action:",
                reply_markup=keyboard,
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text="Your ID is not authorized"
            )
            logger.warning(f"Unauthorized ID: {user_id}")

    async def button_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handles button presses to add a new organization or update existing ones.

        Args:
            update (Update): The update object containing the incoming update.
            context (ContextTypes.DEFAULT_TYPE): The context from the update.
        """
        logger.info("Handling button press")
        query = update.callback_query

        await query.answer()  # unlock the button

        if query.data == "button_add_pressed":
            logger.info(f"Processed {query.data} from user {query.from_user.id}")
            await self.add_company(context, update)

    async def show_unfilled_places(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Displays a message prompting the user to select a location.

        This method sends a message asking the user to select a location when the "Show unfilled places" button is pressed.

        Args:
            update (Update): The update object containing the incoming update.
            context (ContextTypes.DEFAULT_TYPE): The context from the update.
        """
        logger.info("Showing unfilled places")

        # Define the keyboard with a button to request location and an Exit button
        location_button = KeyboardButton(
            text="Share your location", request_location=True
        )
        keyboard = [[location_button], ["Exit"]]

        # Create the ReplyKeyboardMarkup
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )

        # Send the message with the custom keyboard
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Please share your location to find unfilled places near you:",
            reply_markup=reply_markup,
        )

    async def handle_location(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handles the location message sent by the user.

        Args:
            update (Update): The update object containing the incoming message.
            context (ContextTypes.DEFAULT_TYPE): The context from the update.
        """
        user_location = update.message.location
        latitude = user_location.latitude
        longitude = user_location.longitude

        logger.info(f"Received location: latitude={latitude}, longitude={longitude}")

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Thank you! We received your location: latitude={latitude}, longitude={longitude}",
        )

    async def add_company(
        self, context: ContextTypes.DEFAULT_TYPE, update: Update
    ) -> None:
        """
        Handles the addition of a new company to the database.

        Args:
            context (ContextTypes.DEFAULT_TYPE): The context from the update.
            update (Update): The update object containing the incoming update.
        """
        logger.info("Adding company")

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Please enter the name of the company you want to know about.",
            reply_markup=ForceReply(selective=True),
        )

    async def handle_company_name(
        self, update: Update, context: CallbackContext
    ) -> None:
        """
        Handles the input of a company name and retrieves or creates a new card.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """
        logger.info("Handling company name")
        company_name = update.message.text
        logging.info(f"Company name received: {company_name}")

        # Validate company name
        if not self.validate_name(company_name):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Invalid name. Please enter a valid name with only letters, spaces, and apostrophes.",
                reply_markup=ForceReply(selective=True),
            )
            # Request the user to re-enter the company name
            await self.add_company(context, update)
            return  # Exit the function to wait for another input

        sheet = GoogleServices(SHEETS_READ_URL)
        df = sheet.read_from_google_sheets()
        self.current_card_id, flag = GoogleServices.search_name_in_df(df, company_name)
        context.user_data.setdefault("current_card", self.current_card_id)

        if flag:
            message = "Company not found. A new one was created."
        else:
            message = "Company found."

        logger.info(message)

        await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
        await self.show_place_card(update=update, context=context)
        await self.show_editbar(update=update, context=context)
        await self.show_edit_keyboard(update=update, context=context)

    async def show_place_card(self, update: Update, context: CallbackContext) -> None:
        """
        Handles displaying the details of a place card.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """
        logger.info("Displaying place card details")
        current_row = context.user_data["current_card"]

        # Format the information message with all details
        info_message = (
            f"Name: {current_row['name']}\n"
            f"Type: {current_row['type']}\n"
            f"Photos: {current_row['photos']}\n"
            f"Google map: {current_row['google_map']}\n"
            f"Phone numbers: {current_row['phone_numbers']}\n"
            f"WhatsApp: {current_row['Whatsapp']}\n"
            f"Hours of operation: {current_row['hours_of_operation']}"
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=info_message
        )

    async def show_editbar(self, update: Update, context: CallbackContext) -> None:
        """
        Handles displaying an edit bar for the user to select a field to update.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """
        logger.info("Displaying edit bar")
        keyboard_layout = [
            [InlineKeyboardButton("Name", callback_data="name")],
            [InlineKeyboardButton("Type", callback_data="type")],
            [InlineKeyboardButton("Photos", callback_data="photos")],
            [InlineKeyboardButton("Google map", callback_data="google_map")],
            [InlineKeyboardButton("Phone numbers", callback_data="phone_numbers")],
            [InlineKeyboardButton("WhatsApp", callback_data="Whatsapp")],
            [
                InlineKeyboardButton(
                    "Hours of operation", callback_data="hours_of_operation"
                )
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard_layout)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Choose a field to edit:",
            reply_markup=reply_markup,
        )

    async def show_edit_keyboard(
        self, update: Update, context: CallbackContext
    ) -> None:
        """
        Handles displaying a keyboard for the user to confirm or cancel changes.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """
        logger.info("Displaying edit keyboard")
        keyboard = [["Exit", "Save"]]

        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )

        await update.message.reply_text(
            "Save when you are finished, or exit to cancel changes",
            reply_markup=reply_markup,
        )

    async def handle_exit(self, update: Update, context: CallbackContext) -> None:
        """
        Handles the exit command to return to the main menu.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """
        logger.info("Exiting to the main menu")

        context.user_data.clear()
        await update.message.reply_text("You have returned to the main menu")
        await self.start(update=update, context=context)

    async def handle_save(self, update: Update, context: CallbackContext) -> None:
        """
        Handles the '/save' command issued by a user. This command updates a specified field in the database,
        sends notifications about the update, and shows the updated place card to the user.

        This method logs the saving action, sends a reply to the user confirming that the place card has been saved,
        and invokes the display of this place card. It also handles the writing of updated data to Google Sheets and
        manages notifications related to data changes. If data retrieval from Google Sheets is successful, it sends
        a notification; otherwise, it logs the absence of returned data.

        Args:
            update (Update): The update object containing the incoming Telegram update.
            context (CallbackContext): The context from the update, used here for managing asynchronous tasks and data.

        Raises:
            Exception: Logs any exceptions that occur during notification sending or other asynchronous operations.
        """
        logger.info("Saving place card")
        logger.info(f"user ID {update.message.from_user.id}")

        await update.message.reply_text("You saved the place card")
        await self.show_place_card(update=update, context=context)

        send = GoogleServices(SHEETS_READ_URL).write_on_google_sheets(
            organization=context.user_data["current_card"]
        )
        logger.info(f"Old data returned {send}")

        if send != None:
            try:
                await NotificationSender(self.token).send_notification(
                    context.user_data["current_card"], send, update.message.from_user
                )
            except Exception as e:
                logger.error(e)

            context.user_data.clear()
            await self.start(update=update, context=context)
        else:
            logger.info(f"Old data not returned {send}")

    async def handle_new_value(self, update: Update, context: CallbackContext) -> None:
        """
        Handles the input of a new value for the selected field.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """
        logger.info("Handling new value input")
        new_value = update.message.text

        # Check if the command is to show information
        if new_value.lower() == "show information":
            await self.show_place_card(update, context)
        else:
            # Try to update the value in the DataFrame
            try:
                current_row = context.user_data["current_card"]
                logging.info(f"Сurrent_row : {current_row}")

                # Check if the field to update exists in the current row
                if context.user_data["field_to_update"] in current_row:
                    # Perform validation based on the field to update
                    if context.user_data[
                        "field_to_update"
                    ] == "name" and not self.validate_name(new_value):
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text="Invalid name. Please enter a valid name with only letters, spaces, and apostrophes.",
                        )
                        return
                    elif context.user_data["field_to_update"] == "type":
                        if new_value not in ["Places to eat", "Adventures", "Services"]:
                            keyboard_layout = [
                                [
                                    InlineKeyboardButton(
                                        "Places to eat", callback_data="Places to eat"
                                    )
                                ],
                                [
                                    InlineKeyboardButton(
                                        "Adventures", callback_data="Adventures"
                                    )
                                ],
                                [
                                    InlineKeyboardButton(
                                        "Services", callback_data="Services"
                                    )
                                ],
                            ]
                            reply_markup = InlineKeyboardMarkup(keyboard_layout)
                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text="Invalid type. Please choose one of the following types:",
                                reply_markup=reply_markup,
                            )
                            return
                    elif context.user_data["field_to_update"] == "photos":
                        # Photos are handled separately in another method
                        if not update.message.photo or not self.validate_photos(
                            update.message.photo
                        ):
                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text="Invalid photos. Please send valid photo files.",
                            )
                            return
                        new_value = (
                            update.message.photo
                        )  # Update with the actual photo list
                    elif context.user_data[
                        "field_to_update"
                    ] == "google_map" and not self.validate_google_maps(new_value):
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text="Invalid input for google_map. Provide a link to Google Maps using the following format https://maps.app.goo.gl/{LocationID}.",
                        )
                        return

                    elif context.user_data["field_to_update"] in [
                        "phone_numbers",
                        "Whatsapp",
                    ]:
                        # Validate and process phone number
                        digits_only = "".join(filter(str.isdigit, new_value))
                        if len(digits_only) == 8:
                            processed_number = "+506" + digits_only
                        elif len(digits_only) == 11 and digits_only.startswith("506"):
                            processed_number = "+" + digits_only
                        else:
                            processed_number = digits_only
                        new_value = processed_number

                    # Update the value in the dictionary
                    current_row.update(
                        {context.user_data["field_to_update"]: new_value}
                    )
                    # Also update the value in the source dictionary if necessary
                    context.user_data["current_card"][
                        context.user_data["field_to_update"]
                    ] = new_value
                    logger.info("Field updated successfully")
                    # Reset the update field
                    context.user_data.pop("field_to_update")
                    # Display updated information
                    await self.show_place_card(update=update, context=context)
                    await self.show_editbar(update=update, context=context)
                else:
                    logger.warning(
                        f"Invalid field: {context.user_data['field_to_update']}"
                    )
                    # Inform the user if the field is invalid
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"Invalid field: {context.user_data['field_to_update']}",
                    )
            except Exception as e:
                # Handle any exceptions that occur during the update process
                await context.bot.send_message(
                    chat_id=update.effective_chat.id, text=f"Error: {str(e)}"
                )

    async def button(self, update: Update, context: CallbackContext) -> int:
        """
        Handles button presses to select a field to update or type selection.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """
        data = update.callback_query.data

        # Check if the data corresponds to one of the type options
        if data in ["Places to eat", "Adventures", "Services"]:
            # Save the selected type to the current card
            context.user_data["current_card"]["type"] = data
            context.user_data.pop("field_to_update")  # Reset the field to update

            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=f"Type updated to {data}"
            )

            await self.show_place_card(
                update=update, context=context
            )  # Show updated place card
            await self.show_editbar(
                update=update, context=context
            )  # Show edit options again
        else:
            # Handle selection of a field to update
            context.user_data.setdefault("field_to_update", data)
            if context.user_data["field_to_update"] == "type":
                # Display type options for selection
                keyboard_layout = [
                    [
                        InlineKeyboardButton(
                            "Places to eat", callback_data="Places to eat"
                        )
                    ],
                    [InlineKeyboardButton("Adventures", callback_data="Adventures")],
                    [InlineKeyboardButton("Services", callback_data="Services")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard_layout)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Choose a type:",
                    reply_markup=reply_markup,
                )
            else:
                await update.callback_query.answer()
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Enter new value for {context.user_data['field_to_update']}",
                )

    async def add_photo(self, update: Update, context: CallbackContext) -> int:
        """
        Handles button presses to select a photo field to update.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Send photos below and then do /finish",
        )
        return 1

    async def photo_handler(self, update: Update, context: CallbackContext) -> int:
        """
        Handle updates with photo when photo conversation handler running.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """

        user = update.message.from_user.first_name

        photo_file = await update.message.photo[-1].get_file()
        context.user_data.setdefault("photos_received", []).append(photo_file.file_path)
        logger.info(f"{user} added photo {photo_file.file_id}")

        return 1

    async def finish_photo(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> ConversationHandler.END:
        """
        Handle command /finish then start uploading photos from user_data['photos_received']
        by GoogleDrive.upload_photo() and rounding out conversation handler.

        Args:
            update (Update): The update object containing the incoming update.
            context (CallbackContext): The context from the update.
        """

        user = update.message.from_user.first_name

        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Initializing uploading process..."
        )
        try:
            drive = GoogleDrive()
            folder_link = drive.upload_photo(
                folder_name=context.user_data["current_card"]["name"],
                links=context.user_data["photos_received"],
            )
            context.user_data["photos_received"] = []
            context.user_data["current_card"]["photos"] = f"{folder_link}"
            logger.info(f"Photos from {user} successfully uploaded")
        except Exception as ex:
            logging.error(f"Error while GoogleDrive uploading: {ex}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Error while uploading photos, try again",
            )
            await self.show_place_card(update, context)
            await self.show_editbar(update, context)
            return ConversationHandler.END

        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Photos has been uploaded"
        )
        await self.show_place_card(update=update, context=context)
        await self.show_editbar(update=update, context=context)

        return ConversationHandler.END

    def start_bot(self):
        """Starts the bot by setting up handlers and running polling."""
        logger.info("Starting bot...")
        start_handler = CommandHandler("start", self.start)

        button_handler_instance = CallbackQueryHandler(
            self.button_handler, pattern="^button_add_pressed$"
        )

        show_unfilled_handler = CallbackQueryHandler(
            self.show_unfilled_places, pattern="^show_unfilled_places$"
        )

        button_instance = CallbackQueryHandler(
            self.button,
            pattern="^(name|type|google_map|phone_numbers|Whatsapp|hours_of_operation|Places to eat|Adventures|Services)$",
        )

        exit_handler = MessageHandler(filters.Regex("^Exit$"), self.handle_exit)
        save_handler = MessageHandler(filters.Regex("^Save$"), self.handle_save)

        company_name_handler = MessageHandler(
            filters.REPLY & filters.TEXT, self.handle_company_name
        )

        show_info_handler = MessageHandler(
            filters.TEXT & ~filters.COMMAND, self.handle_new_value
        )

        location_handler = MessageHandler(filters.LOCATION, self.handle_location)
        photo_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.add_photo, pattern="photos")],
            states={1: [MessageHandler(filters.PHOTO, self.photo_handler)]},
            fallbacks=[CommandHandler("finish", self.finish_photo)],
            per_user=True,
            per_chat=True,
        )

        self.application.add_handler(start_handler)
        self.application.add_handler(button_handler_instance)
        self.application.add_handler(show_unfilled_handler)
        self.application.add_handler(button_instance)
        self.application.add_handler(exit_handler)
        self.application.add_handler(save_handler)
        self.application.add_handler(company_name_handler)
        self.application.add_handler(show_info_handler)
        self.application.add_handler(location_handler)
        self.application.add_handler(photo_conv_handler)

        try:
            self.application.run_polling()
        except RuntimeError as e:
            logger.error(f"Failed to stop the event loop gracefully: {e}")
