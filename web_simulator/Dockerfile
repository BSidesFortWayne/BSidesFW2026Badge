# syntax=docker/dockerfile:1.6
#
# Build the BSides badge web simulator and serve it with nginx.
# Build context must be the project root (parent of web_simulator/) because
# the build script reads ../src/ alongside web_simulator/.

# ---- build stage ----------------------------------------------------------
FROM emscripten/emsdk:latest AS build

# emscripten/emsdk already ships build-essential, git, make, python3, emcc.

WORKDIR /work
COPY src/ ./src/
COPY web_simulator/ ./web_simulator/

# emsdk image already provides emcc on PATH; tell the build script to use it
# instead of cloning its own emsdk into .deps/.
RUN mkdir -p web_simulator/.deps \
 && ln -s /emsdk web_simulator/.deps/emsdk

RUN bash web_simulator/scripts/build_micropython.sh

# ---- runtime stage --------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

COPY web_simulator/docker/nginx.conf /etc/nginx/conf.d/default.conf

# Static site files
COPY --from=build /work/web_simulator/index.html        /usr/share/nginx/html/
COPY --from=build /work/web_simulator/style.css         /usr/share/nginx/html/
COPY --from=build /work/web_simulator/board_render.png  /usr/share/nginx/html/
COPY --from=build /work/web_simulator/js/               /usr/share/nginx/html/js/
COPY --from=build /work/web_simulator/fonts/            /usr/share/nginx/html/fonts/
COPY --from=build /work/web_simulator/build/            /usr/share/nginx/html/build/

EXPOSE 80
