# tb-go
Traceback go.

Go to lines in a traceback from the command-line.

Warning: this is vibe coded - but will likely get less so over time.


## Motivation
I have been doing vibe code recently and using a full editor feels a bit heavy weight (another window to be aware of). So I am doing more things at the command-line with vim. But clickable tracebacks are really nice so I an adding this the shell.

## Installation
You can install `tb-go` with pipx.

```
pipx install tb-go
```

## Usage
You can run `tb-go` and paste a traceback into it (on linux middle click is your friend here).

Alternatively you can use it as a wrapper with `tb-go python script.py`

I have a snippets with zshnip for this.



## Alternatives and prior work
Python provides programmatic handlers for tracebacks. You could use one of these rather than parsing erorrs.

Many IDEs have this feature. I have implemented it in emacs with compile mode.





