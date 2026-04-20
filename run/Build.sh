sudo ls && cd .. && rm -rf build && mkdir -p build && cd build && cmake .. && cmake --build . --parallel && cp -fv bin/* ../run  && cd ../run && echo "build finished" && ls -l
