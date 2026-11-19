# Security and data flow

The free release supports local devices and direct ADB connections. Cloud-phone provider verification and the paid connector are planned.

| Mode | Where data goes | What is sent or retained |
| --- | --- | --- |
| Free and local | TapHerd data stays on the user's machine. | Device traffic stays local. Screenshots and optional action logs stay local. The free connector collects no telemetry or analytics. |
| Direct ADB to a cloud phone | ADB traffic travels between the user's machine and the cloud-phone provider. | Commands, media, and device responses travel over that connection. Raw ADB over TCP is unencrypted unless the provider protects it with a tunnel. |
| Paid connector | The connector exchanges job definitions and text results with TapHerd cloud. | Screenshot upload defaults to off. Users opt in per device. The cloud automatically deletes each uploaded screenshot after seven days. |

Credentials and provider keys stay on the user's machine in every mode. TapHerd never stores social media passwords. The action log is optional, defaults to off, and stays on the user's machine in all modes.

When enabled, the logger writes a JSONL file per device under the local registry's `logs` directory. Records contain the serial, action name, timestamps, duration, and outcome. View them with `tapherd logs <serial>`.

Android apps can contact their own services, for example when you publish a video. An AI client you configure separately handles any tool results it receives under that client's own data settings.

The Pro notice stores its last display time in the local device registry. `tapherd pro` opens the waitlist at tapherd.info, or the URL you set in `TAPHERD_WAITLIST_URL`, in your browser. The waitlist page has no trackers. It makes no network request until someone submits the signup form. The form sends only the submitted address to the TapHerd waitlist table in Supabase. Visitors can add an address but can't read the list. [Waitlist setup](WAITLIST.md)

## Report a vulnerability

Please report security problems privately, not in a public issue.

- **Preferred:** use GitHub's private vulnerability reporting. On the repository, open **Security → Report a vulnerability** ([direct link](https://github.com/GreenPeaas/tapherd/security/advisories/new)).
- **Email:** security@tapherd.info

Include what's affected, how to reproduce it, and the output of `tapherd --version`. You should get a reply within 3 days. Please give us a reasonable time to ship a fix before you share details publicly.
