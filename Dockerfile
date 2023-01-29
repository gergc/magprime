FROM ghcr.io/magfest/ubersystem:super2020_migrated

# add our code
COPY . plugins/magprime/
RUN if [ -d plugins/magprime/plugins ]; then mv plugins/magprime/plugins/* plugins/; fi
RUN /app/env/bin/paver install_deps
