---
author: Laurence Lawlor
date: MMMM dd, YYYY
paging: Slide %d / %d
---
# Introduction

Hello and welcome to my rw-common walkthrough

---

# Configuration

To configure rw-common install and run the binary

```
rw --help
```

This should give you a `~/.config/rw-common/config.ini`

---

go ahead and check that it is there

---

# Paths

In the config you will need to configure your paths

```
[dirs]
recording_dir = 
lyrics_bin = 
lilypond_dir = 
[recording_settings]
countdown = 
# if recording command is empty default command will be used
# default command is `rec -d -V4`
rec_cmd = rec -d -V4
[submenu_config]
use_less = yes
[setlist]
static = 

```

--- 

recording_dir, lyrics_bin, lilypond_dir
all need to be set to paths on your local disk

---

Finally you will need to add a setlist to go thru

---

Alter your `[setlist]` section in the config.ini with comma separated values


```

[setlist]
static = Song 1, Song 2

```




---
