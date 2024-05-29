"""Send mail"""

#! /usr/bin/env python3

#                                                                                      #
# guiutil: Utilities used by GUI                                                       #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

# smtplib provides functionality to send emails using SMTP.
import smtplib

# MIMEApplication attaching application-specific data (like CSV files) to email messages.
from email.mime.application import MIMEApplication

# MIMEMultipart send emails with both text content and attachments.
from email.mime.multipart import MIMEMultipart

# MIMEText for creating body of the email message.
from email.mime.text import MIMEText

subject = "MapTasker Request/Issue"
body = "This is the body of the text message"
sender_email = "mikrubin@gmail.com"
recipient_email = "mikrubin@gmail.com"
sender_password = "tvybxugbbsxxocqu"  # Application-specific Google app password
smtp_server = "smtp.gmail.com"
smtp_port = 465
path_to_file = "MapTasker_mail.txt"  # This file will be attached.

# MIMEMultipart() creates a container for an email message that can hold
# different parts, like text and attachments and in next line we are
# attaching different parts to email container like subject and others.
message = MIMEMultipart()
message["Subject"] = subject
message["From"] = sender_email
message["To"] = recipient_email
body_part = MIMEText(body)
message.attach(body_part)

# section 1 to attach file
with open(path_to_file, "rb") as file:
    # Attach the file with filename to the email
    message.attach(MIMEApplication(file.read(), Name="example.csv"))

# secction 2 for sending email
with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
    server.login(sender_email, sender_password)
    server.sendmail(sender_email, recipient_email, message.as_string())
