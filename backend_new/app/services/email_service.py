import resend
from app.config import settings


class EmailService:
    def __init__(self):
        resend.api_key = settings.RESEND_API_KEY

    async def send_password_reset(self, to_email: str, reset_url: str) -> None:
        resend.Emails.send({
            "from": f"Big Game Gabe <{settings.EMAIL_FROM}>",
            "to": to_email,
            "subject": "Reset your password — link expires in 60 minutes",
            "html": self._reset_template(reset_url),
        })

    async def send_email_verification(self, to_email: str, verify_url: str) -> None:
        resend.Emails.send({
            "from": f"Big Game Gabe <{settings.EMAIL_FROM}>",
            "to": to_email,
            "subject": "Verify your email to activate your account",
            "html": self._verify_email_template(verify_url),
        })

    def _reset_template(self, url: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Reset your password</title>
</head>
<body style="margin:0;padding:0;background-color:#0a0a0a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#0a0a0a;">
    <tr>
      <td align="center" style="padding:40px 16px;">
        <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="background-color:#111827;border:1px solid #1f2937;border-bottom:none;border-radius:8px 8px 0 0;padding:20px 32px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td>
                    <img src="https://biggamegabetd.app/biggamegabeicon.png" alt="" width="28" height="28"
                      style="display:inline-block;vertical-align:middle;border-radius:4px;" />
                    <span style="display:inline-block;vertical-align:middle;margin-left:10px;color:#ffffff;font-size:17px;font-weight:700;letter-spacing:-0.3px;">Big Game Gabe</span>
                  </td>
                  <td align="right">
                    <span style="color:#a855f7;font-size:11px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;">BGGTDM</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body card -->
          <tr>
            <td style="background-color:#111827;border-left:1px solid #1f2937;border-right:1px solid #1f2937;padding:40px 32px 32px;">

              <!-- Lock icon -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td align="center" style="padding-bottom:24px;">
                    <div style="display:inline-block;width:48px;height:48px;border-radius:50%;border:2px solid #a855f7;text-align:center;line-height:48px;font-size:22px;">
                      &#128274;
                    </div>
                  </td>
                </tr>

                <!-- Headline -->
                <tr>
                  <td align="center" style="padding-bottom:8px;">
                    <span style="color:#ffffff;font-size:24px;font-weight:700;letter-spacing:-0.5px;">Reset your password</span>
                  </td>
                </tr>

                <!-- Subheadline -->
                <tr>
                  <td align="center" style="padding-bottom:32px;">
                    <span style="color:#6b7280;font-size:14px;">This link expires in 60 minutes</span>
                  </td>
                </tr>

                <!-- Body copy -->
                <tr>
                  <td style="padding-bottom:12px;">
                    <p style="margin:0;color:#9ca3af;font-size:15px;line-height:1.6;">
                      Someone requested a password reset for your BGGTDM account. If that was you, use the button below to choose a new password.
                    </p>
                  </td>
                </tr>
                <tr>
                  <td style="padding-bottom:36px;">
                    <p style="margin:0;color:#6b7280;font-size:14px;line-height:1.6;">
                      If you did not request this, you can safely ignore this email. Your account has not been accessed.
                    </p>
                  </td>
                </tr>

                <!-- CTA button -->
                <tr>
                  <td align="center" style="padding-bottom:20px;">
                    <a href="{url}" style="display:inline-block;background-color:#a855f7;color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;padding:14px 40px;border-radius:6px;letter-spacing:0.2px;">Reset Password</a>
                  </td>
                </tr>

                <!-- Fallback URL -->
                <tr>
                  <td align="center" style="padding-bottom:32px;">
                    <p style="margin:0;color:#4b5563;font-size:12px;">Or paste this link into your browser:</p>
                    <p style="margin:4px 0 0;word-break:break-all;"><a href="{url}" style="color:#a855f7;font-size:12px;text-decoration:none;">{url}</a></p>
                  </td>
                </tr>

                <!-- Security strip -->
                <tr>
                  <td style="border-top:1px solid #1f2937;padding-top:20px;">
                    <p style="margin:0;color:#4b5563;font-size:12px;line-height:1.5;">
                      &#128274;&nbsp; This link is single-use and expires in 60 minutes. If you have security concerns, contact support.
                    </p>
                  </td>
                </tr>
              </table>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#0a0a0a;border:1px solid #1f2937;border-top:none;border-radius:0 0 8px 8px;padding:24px 32px;">
              <p style="margin:0;color:#4b5563;font-size:12px;text-align:center;line-height:1.6;">
                Big Game Gabe TD Model &mdash; NFL Touchdown Predictions<br />
                You received this email because an action was taken on your account at
                <a href="https://biggamegabetd.app" style="color:#6b7280;text-decoration:none;">biggamegabetd.app</a>.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    def _verify_email_template(self, url: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Confirm your email</title>
</head>
<body style="margin:0;padding:0;background-color:#0a0a0a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#0a0a0a;">
    <tr>
      <td align="center" style="padding:40px 16px;">
        <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="background-color:#111827;border:1px solid #1f2937;border-bottom:none;border-radius:8px 8px 0 0;padding:20px 32px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td>
                    <img src="https://biggamegabetd.app/biggamegabeicon.png" alt="" width="28" height="28"
                      style="display:inline-block;vertical-align:middle;border-radius:4px;" />
                    <span style="display:inline-block;vertical-align:middle;margin-left:10px;color:#ffffff;font-size:17px;font-weight:700;letter-spacing:-0.3px;">Big Game Gabe</span>
                  </td>
                  <td align="right">
                    <span style="color:#a855f7;font-size:11px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;">BGGTDM</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body card -->
          <tr>
            <td style="background-color:#111827;border-left:1px solid #1f2937;border-right:1px solid #1f2937;padding:40px 32px 32px;">

              <table width="100%" cellpadding="0" cellspacing="0" border="0">

                <!-- Checkmark icon -->
                <tr>
                  <td align="center" style="padding-bottom:24px;">
                    <div style="display:inline-block;width:48px;height:48px;border-radius:50%;border:2px solid #10b981;text-align:center;line-height:48px;font-size:22px;">
                      &#10003;
                    </div>
                  </td>
                </tr>

                <!-- Headline -->
                <tr>
                  <td align="center" style="padding-bottom:8px;">
                    <span style="color:#ffffff;font-size:24px;font-weight:700;letter-spacing:-0.5px;">Confirm your email</span>
                  </td>
                </tr>

                <!-- Subheadline -->
                <tr>
                  <td align="center" style="padding-bottom:32px;">
                    <span style="color:#6b7280;font-size:14px;">One step before you access the model.</span>
                  </td>
                </tr>

                <!-- Body copy -->
                <tr>
                  <td style="padding-bottom:36px;">
                    <p style="margin:0;color:#9ca3af;font-size:15px;line-height:1.6;">
                      You're almost in. Verify your email address to activate your BGGTDM account and start getting weekly touchdown predictions. Your first week's predictions are already queued.
                    </p>
                  </td>
                </tr>

                <!-- CTA button -->
                <tr>
                  <td align="center" style="padding-bottom:20px;">
                    <a href="{url}" style="display:inline-block;background-color:#a855f7;color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;padding:14px 40px;border-radius:6px;letter-spacing:0.2px;">Verify Email Address</a>
                  </td>
                </tr>

                <!-- Fallback URL -->
                <tr>
                  <td align="center" style="padding-bottom:36px;">
                    <p style="margin:0;color:#4b5563;font-size:12px;">Or paste this link into your browser:</p>
                    <p style="margin:4px 0 0;word-break:break-all;"><a href="{url}" style="color:#a855f7;font-size:12px;text-decoration:none;">{url}</a></p>
                  </td>
                </tr>

                <!-- What to expect -->
                <tr>
                  <td style="border-top:1px solid #1f2937;padding-top:24px;">
                    <p style="margin:0 0 12px;color:#6b7280;font-size:12px;font-weight:600;letter-spacing:1px;text-transform:uppercase;">What to expect</p>
                    <p style="margin:0 0 8px;color:#9ca3af;font-size:13px;line-height:1.5;">&mdash; Weekly predictions every Tuesday before kickoff</p>
                    <p style="margin:0 0 8px;color:#9ca3af;font-size:13px;line-height:1.5;">&mdash; Touchdown probability for every active WR and TE</p>
                    <p style="margin:0;color:#9ca3af;font-size:13px;line-height:1.5;">&mdash; Track record updated in real time after each game</p>
                  </td>
                </tr>

              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#0a0a0a;border:1px solid #1f2937;border-top:none;border-radius:0 0 8px 8px;padding:24px 32px;">
              <p style="margin:0;color:#4b5563;font-size:12px;text-align:center;line-height:1.6;">
                Big Game Gabe TD Model &mdash; NFL Touchdown Predictions<br />
                You received this email because you created a BGGTDM account at
                <a href="https://biggamegabetd.app" style="color:#6b7280;text-decoration:none;">biggamegabetd.app</a>.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


email_service = EmailService()
