# Third-party notices

This repository's own code and prose are under the MIT licence in `LICENSE`. The material in the following sections comes from other
projects or is derived from Wube Software's documentation. Files that adapt such material carry a header that points to the source.

## chrisliebaer/factorio-modding-skill

Source: [chrisliebaer/factorio-modding-skill](https://github.com/chrisliebaer/factorio-modding-skill). This project follows
its approach of making the Factorio API documentation grep-friendly. Used under the MIT licence:

```
MIT License

Copyright (c) 2026 Chrisliebär

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Jaer985/factorio-modding-skill

Source: [Jaer985/factorio-modding-skill](https://github.com/Jaer985/factorio-modding-skill). Portable-install notes, the
`--dump-data` and log workflow, and facts about 2.1 breaking changes were adapted from this project after being checked against
Factorio 2.1.21. The files that contain adapted text carry a header naming it. Used under the MIT licence:

```
MIT License

Copyright (c) 2026 gentleman-programming

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Factorio API documentation (Wube Software Ltd.)

The toolkit downloads the JSON behind the [Factorio API documentation](https://lua-api.factorio.com) at run time and caches it
on the user's machine. Short excerpts and facts derived from the API documentation and from the game's `data/changelog.txt`
appear in the references. The documentation is copyright Wube Software Ltd. and is distributed under its
[documentation licence](https://lua-api.factorio.com/latest/license.html), reproduced here:

```
Documentation License [MIT, modified]

Copyright Wube Software Ltd.

Permission is hereby granted, free of charge, to any person obtaining a copy of these documentation files (the "Documentation"), to deal in the Documentation without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Documentation, and to permit persons to whom the Documentation is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Documentation.

THE DOCUMENTATION IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE DOCUMENTATION OR THE USE OR OTHER DEALINGS IN THE DOCUMENTATION.
```

## TalShar783/Factorio-Modding-Skill

Source: [TalShar783/Factorio-Modding-Skill](https://github.com/TalShar783/Factorio-Modding-Skill). Credited as inspiration for
several ideas: preferring generated API stubs for lookups, the caveat that parameter `order` matters, reading the log once
instead of tailing it, putting data stage logic before control stage logic, and keeping a list of approaches known to fail.
That repository carries no licence, so no text or code was copied from it. Every passage in this repository is written
independently.
