# Development image for Arena-Rosnav (branch humble) on ROS 2 Humble.
#
#   ros:humble (Ubuntu 22.04, ROS 2 Humble from apt, Python 3.10)
#   + NVIDIA GPU rendering (OpenGL/EGL/Vulkan through the container toolkit, VirtualGL)
#   + Gazebo Harmonic (OSRF apt), the simulator Arena's humble branch uses
#   + every apt dependency of the workspace resolved by rosdep
#   + Arena's Python dependencies (docker/requirements-arena.txt)
#   + a user with the host's UID/GID and passwordless sudo
#
# Sources are NOT baked in: arena4_ws/ is bind-mounted from the host and built
# with colcon inside the container. Only the package.xml files of
# arena4_ws/src enter the build context (see Dockerfile.dockerignore), so that
# rosdep can install their dependencies here and the result is reproducible.
#
# Build through ../run.sh (context = repository root).
ARG ROS_IMAGE=ros:humble-ros-base-jammy
ARG ISAAC_IMAGE=nvcr.io/nvidia/isaac-sim:4.2.0
# INSTALL_ISAAC=1: take Isaac Sim from NVIDIA's image; 0: an empty directory
ARG INSTALL_ISAAC=1

FROM ${ISAAC_IMAGE} AS isaac-1
FROM busybox:1.36 AS isaac-0
RUN mkdir /isaac-sim
FROM isaac-${INSTALL_ISAAC} AS isaac-src

FROM ${ROS_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=all \
    GAZEBO_VERSION=harmonic \
    GZ_VERSION=harmonic \
    ARENA_ROS_DISTRO=humble

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# ---------------------------------------------------------------- base tools
RUN apt-get update && apt-get install -y --no-install-recommends \
        sudo curl wget gnupg2 lsb-release ca-certificates \
        git git-lfs build-essential cmake pkg-config \
        nano vim less tmux htop psmisc iproute2 iputils-ping bash-completion \
        python3-pip python3-dev python-is-python3 \
        python3-colcon-common-extensions python3-colcon-mixin python3-rosdep \
        ccache \
        # GPU rendering: GLVND dispatch + Vulkan loader (driver libraries are
        # injected at run time by the NVIDIA container toolkit)
        libglvnd0 libgl1 libglx0 libegl1 libgles2 libglu1-mesa libvulkan1 \
        vulkan-tools mesa-utils mesa-utils-extra \
        # X11 / Qt clients (RViz, Gazebo GUI)
        libx11-6 libxext6 libxrender1 libxrandr2 libxi6 libxcursor1 libxinerama1 \
        libxt6 libsm6 libice6 libxkbcommon-x11-0 libxcb-xinerama0 libxcb-cursor0 \
        libfontconfig1 libdbus-1-3 x11-apps x11-utils xauth xvfb \
 && rm -rf /var/lib/apt/lists/*

# Tell GLVND and the Vulkan loader about the NVIDIA driver. The container
# toolkit on this host injects the driver libraries but not these vendor files.
RUN mkdir -p /usr/share/glvnd/egl_vendor.d /etc/vulkan/icd.d \
 && echo '{"file_format_version":"1.0.0","ICD":{"library_path":"libEGL_nvidia.so.0"}}' \
        > /usr/share/glvnd/egl_vendor.d/10_nvidia.json \
 && echo '{"file_format_version":"1.0.0","ICD":{"library_path":"libGLX_nvidia.so.0","api_version":"1.3.277"}}' \
        > /etc/vulkan/icd.d/nvidia_icd.json

# VirtualGL: GPU OpenGL for GUI windows on a remote desktop (ThinLinc/VNC)
# whose X server has no NVIDIA GLX:  vglrun -d egl <program>
ARG VIRTUALGL_VERSION=3.1.1
RUN wget -q https://github.com/VirtualGL/virtualgl/releases/download/${VIRTUALGL_VERSION}/virtualgl_${VIRTUALGL_VERSION}_amd64.deb -O /tmp/vgl.deb \
 && apt-get update && apt-get install -y --no-install-recommends /tmp/vgl.deb \
 && rm -rf /tmp/vgl.deb /var/lib/apt/lists/*

# ---------------------------------------------------------- Gazebo Harmonic
# Same source as Arena's installers/1_gazebo.sh. ros_gz is built from Arena's
# fork in the workspace against this Gazebo (GZ_VERSION=harmonic).
RUN curl -fsSL https://packages.osrfoundation.org/gazebo.gpg \
        -o /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
        > /etc/apt/sources.list.d/gazebo-stable.list \
 && apt-get update && apt-get install -y --no-install-recommends gz-harmonic \
 && rm -rf /var/lib/apt/lists/*
# rosdep rules for the gz-* libraries (gz-sim8, gz-transport13, sdformat14, ...):
# the Humble rosdistro only knows Fortress. Documented by Gazebo for building
# ros_gz from source against a non-default Gazebo release.
RUN curl -fsSL https://raw.githubusercontent.com/osrf/osrf-rosdep/master/gz/00-gazebo.list \
        -o /etc/ros/rosdep/sources.list.d/00-gazebo.list

# ------------------------------------------------- non-rosdep build deps
# lightsfm (header-only social force model) is needed by hunav_sim and
# hunav_gz_plugin; Arena's install.sh installs it with `make install` too.
ARG LIGHTSFM_COMMIT=b30327c
RUN git clone https://github.com/robotics-upo/lightsfm.git /tmp/lightsfm \
 && cd /tmp/lightsfm && git checkout ${LIGHTSFM_COMMIT} && make install \
 && rm -rf /tmp/lightsfm

# vcstool fork used by Arena: understands the "branch@commit" pins in .repos
RUN pip3 install --no-cache-dir git+https://github.com/voshch/vcstool.git

# Arena's Python dependencies
COPY docker/requirements-arena.txt /tmp/requirements-arena.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements-arena.txt && rm /tmp/requirements-arena.txt

# ------------------------------------------------------- Isaac Sim (optional)
# Isaac Sim 4.2.0 = the version Arena's installers/2_isaac.sh installs (as the
# standalone build in ~/isaacsim-4.2.0 + pip packages from pypi.nvidia.com).
# On this network NVIDIA's download hosts are TLS-intercepted by the campus
# firewall, so the identical standalone build is copied from NVIDIA's official
# container (nvcr.io), see the isaac-* stages at the top. Used by `sim:=isaac`
# (package ros2isaacsim). Build with INSTALL_ISAAC=0 to leave it out.
# Isaac Sim is covered by the NVIDIA Omniverse EULA, accepted at run time
# through OMNI_KIT_ACCEPT_EULA / ACCEPT_EULA (compose.yaml).
# owned by the user: Isaac writes caches/logs inside its install tree
ARG USER_UID=1000
ARG USER_GID=1000
COPY --from=isaac-src --chown=${USER_UID}:${USER_GID} /isaac-sim /opt/isaac-sim
RUN if [ -f /opt/isaac-sim/setup_python_env.sh ]; then \
        apt-get update && apt-get install -y --no-install-recommends libfuse2 libxt6 libglu1-mesa \
     && rm -rf /var/lib/apt/lists/* ; \
    fi

# --------------------------------------------------- rosdep (workspace deps)
# Only package.xml / *_IGNORE files of arena4_ws/src are in the context.
# setup.bash provides ROS_VERSION/ROS_PYTHON_VERSION for package.xml
# conditions; GZ_VERSION (above) selects the Harmonic deps of ros_gz.
# Skipped keys and why: docker/rosdep-skip-keys.txt
COPY docker/rosdep-skip-keys.txt /tmp/rosdep-skip-keys.txt
COPY arena4_ws/src /tmp/arena_src
RUN . "/opt/ros/${ROS_DISTRO}/setup.bash" \
 && apt-get update \
 && rosdep update --rosdistro "${ROS_DISTRO}" \
 && rosdep install --from-paths /tmp/arena_src --ignore-src --rosdistro "${ROS_DISTRO}" -y \
        --skip-keys "$(sed 's/#.*//' /tmp/rosdep-skip-keys.txt | xargs)" \
 && rm -rf /tmp/arena_src /tmp/rosdep-skip-keys.txt /var/lib/apt/lists/*

# ------------------------------------------- NVIDIA OptiX / NGX (optional)
# RTX denoiser (OptiX) and DLSS (NGX) for Isaac Sim. Must match the host driver
# version exactly; run.sh fetches them for the running driver into
# docker/nvidia-extra/ (empty directory = skipped).
COPY docker/nvidia-extra/ /tmp/nvidia-extra/
RUN cd /tmp/nvidia-extra \
 && L=/usr/lib/x86_64-linux-gnu \
 && for f in libnvoptix.so.* libnvidia-ngx.so.*; do [ -f "$f" ] && cp "$f" $L/; done; \
    if [ -f nvoptix.bin ]; then mkdir -p /usr/share/nvidia && cp nvoptix.bin /usr/share/nvidia/ && cp nvoptix.bin $L/; fi; \
    for f in $L/libnvoptix.so.[0-9]*.* $L/libnvidia-ngx.so.[0-9]*.*; do \
        [ -f "$f" ] && ln -sf "$(basename "$f")" "${f%%.so.*}.so.1"; done; \
    ldconfig && rm -rf /tmp/nvidia-extra && (ldconfig -p | grep -E "nvoptix|nvidia-ngx" || true)

# -------------------------------------------------------------- user
# Same UID/GID as the host user, so files written into bind mounts keep their
# owner. Passwordless sudo is for installing extra packages while experimenting;
# anything that must persist belongs in this Dockerfile.
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000
RUN (getent group ${USER_GID} || groupadd --gid ${USER_GID} ${USERNAME}) \
 && useradd --uid ${USER_UID} --gid ${USER_GID} --create-home --shell /bin/bash ${USERNAME} \
 && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} \
 && chmod 0440 /etc/sudoers.d/${USERNAME}

# Every interactive shell gets the ROS 2 + Arena environment. The script lives
# in the bind-mounted repository, so edits apply without rebuilding.
RUN echo '[ -f "$WM_PROJECT_DIR/docker/arena_env.bash" ] && . "$WM_PROJECT_DIR/docker/arena_env.bash"' \
        >> /etc/bash.bashrc

USER ${USERNAME}
WORKDIR /home/${USERNAME}
# The build/install/log directories exist in the image so that the named
# volumes mounted there (compose.yaml) are initialised as owned by the user.
RUN mkdir -p ~/.ros ~/.cache ~/.local/bin \
        ~/wm_social_robot/arena4_ws/build ~/wm_social_robot/arena4_ws/install ~/wm_social_robot/arena4_ws/log \
 && rosdep update --rosdistro "${ROS_DISTRO}" >/dev/null
ENTRYPOINT []
CMD ["sleep", "infinity"]
