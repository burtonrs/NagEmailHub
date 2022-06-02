#!/usr/bin/python3

###############################################################################
#
# Program: nagemail.py
# Author:  Brian Welch
# 
# Purpose:
#
#  This program reads the daily "ssl certs exp" email from Dashboard and sends
#  a reminder email to the contact specified in the "Supported by" column.
#
#  Changes:
#
#  Date        by whom        change
#-----------------------------------------------------------------------
# 08/17/2017   Brian Welch    Initial coding
# 02/13/2018   Brian Welch    Changed email to groups who install their own certs
#
############################################################################### 

import csv
import logging
import os
import re
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from time import gmtime, strftime

# Todo:
# - Add support for sending email to multiple addresses


DEFAULT_SENDER = os.getenv("DEFAULT_SENDER", "example@example.com")
EMAIL_SERVER = os.getenv("EMAIL_SERVER", "localhost")
EMAIL_SERVER_PORT = os.getenv("EMAIL_SERVER_PORT", 25)

def send_email(recipient, message = "<b>Hello!</b>", sender = DEFAULT_SENDER, subject = "", server = EMAIL_SERVER, server_port = EMAIL_SERVER_PORT):
    if not isinstance(recipient, str):
        raise Exception("Email recipient must be a string")
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient
    # msg.attach(MIMEText(message, "plain"))
    msg.attach(MIMEText(message, "html"))
    with smtplib.SMTP(server, server_port) as smtp:
        logging.debug("Connecting to smtp server: %s %s" % smtp.noop())
        smtp.sendmail(sender, recipient, msg.as_string())
        logging.info("Email sent to %s" % recipient)

# Created a small "test version" of the all URLs csv file. The REAL .csv is /tmp/sslcertcheckpeek2_allurls.csv
#infile = "/tmp/sslcertcheckpeek2_alllurls.csv"
infile = os.getenv("INFILE", "nagemail_testing_variables.csv")
sentlog = os.getenv("SENTLOG", "nagemail_already_sent.log")
sentloglist = os.getenv("SENTLOGLIST", "sltemp.txt")
nagemail_body = os.getenv("NAGEMAIL_BODY", "nagemail.body")
notify_only_body = os.getenv("NOTIFY_ONLY_BODY", "nagemail_notify_only.body")
cdb_error_body = os.getenv("CDB_ERROR_BODY", "nagemail_cdb_error.body")
email_server = os.getenv("EMAIL_SERVER", "localhost")
appinfemail = os.getenv("APPINFEMAIL", "RIS-GLOAppInf@risk.lexisnexis.com")
recipients_error = os.getenv("RECIPIENTS_ERROR", "richard.burton@lexisnexisrisk.com")
timestamp = strftime("%Y-%m-%d--%H-%M-%S", gmtime())
logfile = os.getenv("LOGFILE", "nagemail_"+timestamp+".log")

# Number of days before we resend a nagemail reminder
resenddays = 7

print("Using SMTP server %s" % email_server)

logging.basicConfig(filename=logfile, filemode='a', format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG)

logging.debug("Starting")
# This is the list which contains all SSL certs that we want to examine 
sslcertlist = []
# This is the list which contains all systems which are not listed as "good" in the CDB file
badlist = []
linecount = 0
previouscommonname = ""

if not os.path.exists(sentlog):
    with open(sentlog, mode="a"):
        pass

logging.debug(sentlog)
resenddays -= resenddays
if os.path.exists(sentloglist):
    os.remove(sentloglist)

SENTLOG = open(sentlog, 'r')
sentloglines = SENTLOG.readlines()
SENTLOG.close()

SENTLOGLIST = open(sentloglist, 'w')

sentlogarray = []
now = int(time.time())
limit = now - (resenddays * 86400)
for line in sentloglines:
    logging.debug("SentLogLine="+line)
    # Verify this line contains only sentdate, sentowner, sentcommonname
    spaces = line.count(" ")
    if (spaces == 2):
        sentdate, sentowner, sentcommonname = line.split()
    else:
        continue
    sentdate = float(sentdate)
    if (sentdate > limit):
        SENTLOGLIST.writelines(line)
        sentlogarray.append(sentcommonname)

##########################################################
# Import Data from .csv file
##########################################################

with open(infile) as csvfile:
    csvlines = csv.reader(csvfile, delimiter=',')
    for row in csvlines:
        linecount += 1
        logging.debug("Opened File")
        logging.debug("LINE "+str(linecount)+"\n")
        logging.debug(row)
        # skip over the header row
        if (linecount == 1): 
            continue
        # Initialize variables for each row
        url = ""
        infoerror = ""
        commonname = ""
        exp = ""
        issuer = ""
        days = ""
        copy2customer = ""
        checked = ""
        supportedby = ""
        businessunit = ""
        dashboard = ""
        lifecycle = ""
        installer = ""
        tik = ""

        # Create a variable for each element of the row 
        # (we won't use them all currently, but in the future, who knows?)
        url = row[0]
        infoerror = row[1]
        commonname = row[2]
        exp = row[3]
        issuer = row[4]
        days = row[5]
        copy2customer = row[6]
        checked = row[7]
        supportedby = row[8]
        if supportedby.isspace():
            supportedby = ""
        businessunit = row[9]
        dashboard = row[10]
        lifecycle = row[11]
        installer = row[12]
        tik = row[13]
        if tik.isspace():
            tik = ""

        # Create a dictionary of this row
        sslcertline = {
            'URL'           : url,
            'INFOERROR'     : infoerror,
            'COMMONNAME'    : commonname,
            'EXP'           : exp,
            'ISSUER'        : issuer,
            'DAYS'          : days,
            'COPY2CUSTOMER' : copy2customer,
            'CHECKED'       : checked,
            'SUPPORTEDBY'   : supportedby,
            'BUSINESSUNIT'  : businessunit,
            'DASHBOARD'     : dashboard,
            'LIFECYCLE'     : lifecycle,
            'INSTALLER'     : installer,
            'TICKET'        : tik
        }

        # If this line has a new common name or the common name is blank, add this line to the list
        if (previouscommonname != commonname):
            sslcertlist.append(sslcertline)
            previouscommonname = commonname
        elif (commonname == "&nbsp;"):
            sslcertlist.append(sslcertline)

        if (infoerror != "good"):
            badlist.append(sslcertline)

##################################################################
# Generate the Nag Email
##################################################################

_15daycount = 0
_30daycount = 0
_60daycount = 0
_90daycount = 0
_120daycount = 0
blanksupport = 0
invalidsupport = 0
blankinstaller = 0
invalidinstaller = 0
emailSentTo = ""
invalidbody = ""

for cert in sslcertlist[:]:
    _15day = 0
    _30day = 0
    _60day = 0
    _90day = 0
    _120day = 0
    appinfinstall = False 
    bademail = False
    print (cert)
    logging.debug(cert)
    
    thisurl = str(cert['URL'])
    logging.debug("NAGEMAIL: url="+thisurl)    
    thisinfoerror = cert['INFOERROR']
    logging.debug("NAGEMAIL: infoerror="+thisinfoerror)
    thiscommonname = cert['COMMONNAME']
    logging.debug("NAGEMAIL: commonname="+thiscommonname)
    thisexp = cert['EXP']
    logging.debug("NAGEMAIL: expiration="+thisexp)
    thisissuer = cert['ISSUER']
    logging.debug("NAGEMAIL: issuer="+thisissuer)
    thisdays = cert['DAYS']
    logging.debug('NAGEMAIL: days='+thisdays)
    thiscopy2customer = cert['COPY2CUSTOMER']
    logging.debug("NAGEMAIL: copy2customer"+thiscopy2customer)
    thischecked = cert['CHECKED']
    logging.debug("NAGEMAIL: checked="+thischecked)
    thissupportedby = cert['SUPPORTEDBY']
    logging.debug("NAGEMAIL: supportedby="+thissupportedby)
    thisbusinessunit = cert['BUSINESSUNIT']
    logging.debug("NAGEMAIL: businessunit="+thisbusinessunit)
    thisdashboard = cert['DASHBOARD']
    logging.debug("NAGEMAIL: dashboard="+thisdashboard)
    thislifecycle = cert['LIFECYCLE']
    logging.debug("NAGEMAIL: lifecycle="+thislifecycle)
    thisinstaller = cert['INSTALLER']
    logging.debug("NAGEMAIL: installer="+thisinstaller)

    thisticket = cert['TICKET']
    logging.debug("NAGEMAIL: ticket="+thisticket)
    
    if supportedby.isspace():
        badaddr = "Blank Support Address"
        bademail = True
        blanksupport += blanksupport
        logging.debug("Bad supportedby="+supportedby)
   
    # Regex to check for a valid email addresses
    emailRegex = "(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
    if not (re.search(emailRegex,supportedby)):
        badaddr = supportedby
        bademail = True
        supportedby = "Email address invalid (malformed): "+supportedby
        logging.debug("Bad supportedby="+supportedby)

    if installer.isspace():
        badaddr = "Blank Installer Address"
        bademail = True
        blankinstaller += blankinstaller
        logging.debug("Bad installer="+installer)

    if not (re.search(emailRegex,installer)):
        badaddr = installer
        bademail = True
        supportedby = "Email address invalid (malformed): "+installer
        logging.debug("Bad installer="+installer)

    certexpnotice = ""

    # Create a notificaton to go into the log
    thisdays = float(thisdays)
    thisdays = int(round(thisdays))
    if (thisdays <= 15):
        certexpnotice = "15 days or less before the cert expires"
        _15daycount += _15daycount
        _15day = True
    elif (thisdays <= 30):
        certexpnotice = "30 days to 16 days before the cert expires"
        _30daycount += _30daycount
        _30day = True
    elif (thisdays <= 60):
        certexpnotice = "60 days to 31 days before the cert expires"
        _60daycount += _60daycount
        _60day = True
    elif (thisdays <= 90):
        certexpnotice = "90 days to 61 days before the cert expires"
        _90daycount += _90daycount
        _90day = True
    elif (thisdays <= 120):
        certexpnotice = "120 days to 91 days before the cert expires"
        _120daycount += _120daycount
        _120day = True
        
    # Log the information about this cert
    if (certexpnotice != ""):
        logging.info("Cert expirint: "+certexpnotice)
        logging.info("URL is: "+thisurl)
        logging.info("Common Name is: "+thiscommonname)
        logging.info("Expiration Date is: "+str(thisexp))
        logging.info("Expiration Days: "+str(thisdays))
        logging.info("Supported By Email is: "+thissupportedby)
        logging.info("Installed By is: "+thisinstaller)

        # Create the subject for the Nag Email
        subject_out = "test-SSL Certificate for "+thiscommonname+" Expires on "+str(thisexp)+" - ["+str(thisdays)+" Days]"
    else:
        # If over 120 days out, go to next cert (no email)
        logging.info("ERROR: Expiraton Days = "+thisdays)
        logging.info("No email sent - over 120 days.")
        if not bademail:
            continue

    # If there is a current iSIT ticket for this common name and no problem with the 
    # "Supported By" field, then go to the next line (no email)
    if (thisticket != ""):
        logging.info("Ticket exists: "+thisticket)
        logging.info("No email sent - ticket exists.\n")
        if not bademail:
            continue

    # If date is more than 90 days out and no problem with the "Supported By" field, 
    # then go to next line (no email)
    if (_120day):
        logging.info("No email sent - over 90 days.\n")
        if not bademail:
            continue

    # Otherwise, process this line
    if not bademail:
        if _90day or _60day or _30day or _15day:
            # Check if 2 weeks to expiration or no notification sent in past week
            # We will send an email if either of these conditions is true
            if _15day or not (thiscommonname in sentlogarray):
                if _15day:
                    logging.info("\nCert expires in 15 days or less.")
                else:
                    logging.info("\nEmail not sent in "+resenddays+" days.")

                logging.info("Sending email to: "+thissupportedby)
                logging.info("With subject: "+subject_out+"\n")

                if thisinstaller.lower() == appinfemail.lower():
                    
                    #############################################################
                    # If installer is the Application Infrastructure group,
                    # we will send a full Nag Email, using the file nagemail.body
                    # This is a text file with the xml for the pretty email
                    # which gets sent out to most customers.
                    #############################################################

                    with open(nagemail_body, 'r') as infile:
                        data = infile.read()

                    message = data.format(expdate = thisexp, commonname = thiscommonname, ticket = thisticket)
                    emailSentTo = emailSentTo+thisdays+" day email being sent to "+thissupportedby+" for Common Name "+thiscommonname+"\n"
                else:
                    
                    #############################################################
                    # We will send the "notify only" Nag Email,
                    # using the file nagemail_notify_only.body
                    #############################################################

                    with open(notify_only_body, 'r') as infile:
                        data = infile.read()

                    message = data.format(expdate = thisexp, commonname = thiscommonname, ticket = thisticket)
                    with open('message.html', 'w') as f:
                        f.write(message)
                    emailSentTo = emailSentTo + str(thisdays) + " day email being sent to installer "+thissupportedby+" for Common Name "+thiscommonname+"\n"

                #########################################################
                # Send Nag Email or Notify Email
                ########################################################
                send_email(thissupportedby, message = message, subject = subject_out)

                SENTLOG = open(sentlog, 'a')
                SENTLOG.write(str(now)+" "+thissupportedby+" "+thiscommonname)
            else:
                logging.info("No email sent - Less than "+resenddays+" days since last email.\n")
        else:
                logging.info("No email sent - Not 90, 60 or 30 days to expiration.\n")
    else:
        logging.info("Adding email address to list of blank/malformed addresses.\n")
        invalidrecord = "<tr><td>"+thisurl+"</td><td>"+thiscommonname+"</td><td>"+str(thisexp)+"</td><td>"+str(thisdays)+"</td><td>"+badaddr+"</td></tr>"
        logging.debug("invalidrecord="+invalidrecord)
        invalidbody = invalidbody+invalidrecord
        logging.debug("invalidbody="+invalidbody)


#########################################################
# Email App Inf team with errors found in email
#########################################################

if invalidsupport > 0:
    with open(cdb_error_body, 'r') as infile:
        data = infile.read()

    message = data.format(invalid = invalidbody)
    logging.info("Errors found in Dashboard. Emailing summary of errors to App Inf.")
    logging.info("Sending email to: "+recipients_error)
    send_email(recipients_error, message, subject = subject_out)


######################################################################
# Email Report of URLs Which are Not Reporting Information in the CDB
######################################################################

# Record invalid entries in "invalidbody" variable.
invalidbody = ""
for cert in sslcertlist[:]:
    url = str(cert['URL'])
    logging.debug("NON-REPORTING: url="+url)
    infoerror = cert['INFOERROR']
    logging.debug("NON-REPORTING: infoerror="+infoerror)
    commonname = cert['COMMONNAME']
    logging.debug("NON-REPORTING: commonname="+commonname)
    supportedby = cert['SUPPORTEDBY']
    logging.debug("NON-REPORTING: supportedby="+supportedby)
    installer = cert['INSTALLER']
    logging.debug("NON-REPORTING: installer="+installer)

    if infoerror != "good":
        invalidbody = invalidbody+url+"  "+infoerror+"  "+commonname+"  "+supportedby+"  "+installer+"<br>"

# If we found some invalid entries, email them
if invalidbody != "":
    with open(cdb_error_body, 'r') as infile:
        data = infile.read()
    message = data.format(invalid = invalidbody)
    logging.info("Supported By Errors found in Dashboard. Emailing summary of errors to App Inf.")
    logging.info("Sending email to: "+recipients_error)
    send_email(recipients_error, message, subject = subject_out)

SENTLOGLIST.close()
SENTLOG.close()
