# BGC Viewer

A viewer for biosynthetic gene cluster (BGC) data.


## Installation & run

Using Python 3.11 or higher, install and run the BGC Viewer as follows:

```bash
pip install bgc-viewer
bgc-viewer
```

This will start the BGC Viewer server, to which you can connect with your web browser.


## Configuration

Environment variables can be set to change the configuration of the viewer.
A convenient way to change them is to put a file called `.env` in the directory from
which you are running the application.

- `BGCV_HOST` - Server host (default: localhost)
- `BGCV_PORT` - Server port (default: 5005)
- `BGCV_DEBUG_MODE` - Enable dev/debug mode (default: False)


## License

Apache 2.0
