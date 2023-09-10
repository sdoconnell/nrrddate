# The nrrdtools suite
`nrrdbook`, `nrrddate`, `nrrdtask`, `nrrdalrt`, `nrrdnote`, `nrrdjrnl`, `nrrdmark`, and `nrrdtime` are collectively applications in the `nrrdtools` suite. These applications share similar design principles, similar command syntax and UI, and (in some cases) interoperate with each other.

## Why I wrote these applications
I generally prefer simpler, text-oriented, keyboard-driven interfaces. I'm also a sucker for integrated application platforms. In terms of application availability, those two aspects seem to be mutually exclusive. For years, I've either accepted the UI/UX inefficiencies of GUI applications or accepted the lack of integration and design consistency while using a disparate collection of terminal-based applications to accomplish the tasks I need to perform. That kind of sucked, and so I eventually decided to build my own integrated platform of terminal-based applications that would meet my specific needs and adhere to my own preferences. `nrrdtools` is the result of that hubris.

## Why I distribute these applications
The `nrrdtools` applications are decidedly opinionated in that they are written to meet my own needs in the manner that I prefer. At the end of the day I wrote these programs for myself, and would have written them regardless. But since that work has already been done why not share the code so that others may use it also? Perhaps I'm not the only one with the itch these particular programs scratch. And so I make the applications available for others to use, modify, extend, etc.

I'm paying back for all the FOSS I've used over the years and continue to use, and paying forward for the FOSS I'll use in the future. I sincerely hope others can find use and enjoyment from the software I've written, as I've found use and enjoyment from the work of others.

That said, I am not a software vendor and you are not my customer. As specified in the license, these applications are provided in the hope that they will be useful BUT without any warranty, even that of fitness for purpose. In other words, if these programs work for you and meet *your* needs as well as mine - that's gravy. If not, then better luck next time, I guess?

## Contributing
### Core principles
There are a number of guiding principles in the design of the `nrrdtools` applications. Before submitting contributions in the form of ideas, suggestions, or patches - please familiarize yourself with these concepts:

0. The applications should run in any POSIX-standard shell/terminal.
1. The applications should be command-oriented in a manner similar to natural language, but with shortcuts for common functions.
2. The applications should offer as much freedom as possible/practical to the user to customize the application experience (e.g., file locations, colors, functionality, mode of operation, etc.).
3. The applications should store their data in a plain-text format and should allow the user (even if as a last resort) to directly view and manipulate the application data in their preferred text editor, or to interact with the application data using standard text-manipulation tools (`grep`, `sed`, `awk`, etc.).
4. The data storage format should be atomic - one record, one file - in order to facilitate backup and synchronization using standard file management tools.
5. The applications should be extensible, with a means to output data in a structured form digestable by third-party scripts and applications.
6. The applications should be desktop-first, with mobile device integration a distant (or non-) consideration.

### Bug reports
Useful bug reports are welcome. A *useful* bug report will include the following detail:

- Your operating system name and version.
- Your installed Python version.
- The installed versions of any Python dependency libraries specified in `requirements.txt`.
- A detailed description of the bug and how to reproduce the bad behavior.
- Contact information so that I can follow-up with you for further testing or if I have additional questions about your bug.

A *not-useful* bug report will contain a one-liner such as "*yur app is br0k3n! pls fix it quik!!!*". Unfortunately, *not-useful* bug reports are vulnerable to a bug in the bug-reporting system that causes such bug reports to be routed to `/dev/null`. I've not yet found the time to isolate and fix that bug deletion bug, perhaps one day. In the meantime, it's best to avoid that bug reporting bug by ensuring that your submitted bug reports are classified as *useful*.

### Feature requests vs bug reports
**Bug report**: "*The documentation says the program should do X when I do Y, and it does Z instead of Y. Either this behavior is unintended or the documentation is incorrect.*"

**Feature request**: "*The program does X when I do Y, but I think it would be way cooler if it did Z instead of Y, or if it also did W.*"

Feature requests absent of a patch are filed as "lowest priority".

### Pull Requests
Help with improving the `nrrdtools` applications is welcome. Please be sure to review the project's [Core principles](#core-principles) above. If you have an idea for a feature or improvement that you would like to see merged into a `nrrdtools` application, you might want to first reach out to me via [email](mailto:sean@sdoconnell.net) and discuss your idea or feature prior to committing work.

#### Submitting a PR
I do ask that you be patient and considerate of my time in processing your PR. I *will* review it but I may not be able to do so immediately or get back to you right away. I also make no guarantees regarding whether or not a PR will eventually be merged. I may like your idea or I may not. I may like your idea but see issues with your implementation, or I may choose not to merge it for some other reason. Whatever the case please remain civil about it. At the end of the day, remember that `nrrdtools` is a Open Source project and that you're free to fork these applications, add your own patches, etc., as long as you adhere to the terms of the license.

### Areas of concern
The following items are currently the most in need of contribution (in order of priority):

- QA and bug reports
- Documentation
- Unit tests

### Areas of non-concern
Mobile integration of `nrrdtools` via protocols such as [CardDAV](https://en.wikipedia.org/wiki/CardDAV) and [CalDAV](https://en.wikipedia.org/wiki/CalDAV) are of little concern to me, personally. To be completely forthcoming, I find both "standards" to be something of a trainwreck - in implementation compliance, if not in design.

I'll likely not be working on CardDAV/CalDAV support anytime soon (if ever), but should someone else be so inclined I'll not discount their effort out of hand. That said, I do not envision sync protocol support being incorporated directly into the `nrrdtools` applications themeselves but rather implemented in a separate daemon that reads and writes `nrrdtools` data files and translates changes to a DAV host (e.g., `nrrdsync`). This would be similar to the way `nrrdalrt` runs in the background, reads reminders from `nrrddate` and `nrrdtask`, and handles notifications for the two applications.

Any efforts on DAV sync should be focused in that general direction unless and until someone convinces me otherwise.

