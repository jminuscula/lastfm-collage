# lastfm-collage
Create a collage with cover art from your last.fm scrobblings

Requires [ImageMagick's](http://www.imagemagick.org/) montage

## Usage

```
$ ./top-albums.py -n 140 -a <lastfm_user1> <lastfm_user2> > topalbums.txt

$ ./download-covers.py topalbums.txt -o covers

$ montage covers/* -geometry 640x640 -tile 10x14 poster.png
```
