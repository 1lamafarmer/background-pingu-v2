import semver, re, requests
from packaging import version
from BackgroundPingu.bot.main import BackgroundPingu
from BackgroundPingu.core.parser import Log, ModLoader, OperatingSystem

class IssueBuilder:
    def __init__(self, bot: BackgroundPingu, log: Log) -> None:
        self.bot = bot
        self._messages = {
            "top_info": [],
            "error": [],
            "warning": [],
            "note": [],
            "info": []
        }
        self.log = log
        self.amount = 0
        self._last_added = None
    
    def _add_to(self, type: str, value: str, add: bool=False):
        self._messages[type].append(value)
        if not add:
            self.amount += 1
            self._last_added = type
        return self

    def top_info(self, key: str, *args):
        return self._add_to("top_info", "‼️ **" + self.bot.strings.get(f"top_info.{key}", key).format(*args) + "**")

    def error(self, key: str, *args):
        return self._add_to("error", "<:dangerkekw:1123554236626636880> " + self.bot.strings.get(f"error.{key}", key).format(*args))
    
    def warning(self, key: str, *args):
        return self._add_to("warning", "<:warningkekw:1123563914454634546> " + self.bot.strings.get(f"warning.{key}", key).format(*args))
    
    def note(self, key: str, *args):
        return self._add_to("note", "<:kekw:1123554521738657842> " + self.bot.strings.get(f"note.{key}", key).format(*args))

    def info(self, key: str, *args):
        return self._add_to("info", "<:infokekw:1123567743355060344> " + self.bot.strings.get(f"info.{key}", key).format(*args))

    def add(self, key: str, *args):
        return self._add_to(self._last_added, "<:reply:1121924702756143234>*" + self.bot.strings.get(f"add.{key}", key).format(*args) + "*", add=True)

    def has(self, type: str, key: str) -> bool:
        key = self.bot.strings.get(f"{type}.{key}", key)
        for string in self._messages[type]:
            if key == str(string).split(" ", 1)[1]:
                return True
        return False

    def has_values(self) -> bool:
        return self.amount > 0

    def build(self) -> list[str]:
        messages = []
        index = 0
        for i in self._messages:
            for j in self._messages[i]:
                add = j + "\n" + ("\n" if i == "top_info" and index == len(self._messages[i]) - 1 else "")
                if len(messages) == 0 or index % 9 == 0: messages.append(add)
                else: messages[len(messages) - 1] += add
                index += 1
        return messages

class IssueChecker:
    def __init__(self, bot: BackgroundPingu, log: Log) -> None:
        self.bot = bot
        self.log = log
        self.java_17_mods = [
            "antiresourcereload",
            "serversiderng",
            "setspawnmod",
            "peepopractice",
            "areessgee"
        ]
        self.assume_as_latest = [
            "sodiummac",
            "serversiderng",
            "lazystronghold",
            "krypton",
            "sodium-fabric-mc1.16.5-0.2.0+build.4",
            "optifine",
            "sodium-extra",
            "biomethreadlocalfix",
            "forceport",
            "sleepbackground-3.8-1.8.x-1.12.x",
            "tab-focus"
        ]
        self.assume_as_legal = [
            "mcsrranked",
            "mangodfps",
            "serversiderng"
        ]
        self.mcsr_mods = [
            "worldpreview",
            "anchiale",
            "sleepbackground",
            "StatsPerWorld",
            "z-buffer-fog",
            "tab-focus",
            "setspawn",
            "SpeedRunIGT",
            "standardsettings",
            "forceport",
            "lazystronghold",
            "antiresourcereload",
            "extra-options",
            "chunkcacher",
            "serverSideRNG",
            "peepopractice",
            "fast-reset",
            "mcsrranked"
        ]
    
    def get_mod_metadata(self, mod_filename: str) -> dict:
        mod_filename = mod_filename.lower().replace("optifine", "optifabric")
        filename = mod_filename.replace(" ", "").replace("-", "").replace("+", "").replace("_", "")
        for mod in self.bot.mods:
            original_name = mod["name"].lower()
            mod_name = original_name.replace(" ", "").replace("-", "").replace("_", "")
            mod_name = "zbufferfog" if mod_name == "legacyplanarfog" else mod_name
            mod_name = "dynamicmenufps" if mod_name == "dynamicfps" else mod_name
            if mod_name in filename: return mod
        return None
    
    def get_latest_version(self, metadata: dict) -> bool:
        if self.log.minecraft_version is None: return None
        formatted_mc_version = self.log.minecraft_version
        if formatted_mc_version.count(".") == 1: formatted_mc_version += ".0"
        try: minecraft_version = semver.Version.parse(formatted_mc_version)
        except: return None
        latest_match = None
        for file_data in metadata["files"]:
            for game_version in file_data["game_versions"]:
                all_versions = game_version.split(" ")
                for version in all_versions:
                    try:
                        if minecraft_version.match(version):
                            latest_match = file_data
                            if str(minecraft_version) in version:
                                return latest_match
                    except ValueError: continue
        return latest_match

    def check(self) -> IssueBuilder:
        builder = IssueBuilder(self.bot, self.log)

        is_mcsr_log = any(self.log.has_mod(mcsr_mod) for mcsr_mod in self.mcsr_mods) or self.log.minecraft_version == "1.16.1"
        found_crash_cause = False
        illegal_mods = []
        checked_mods = []
        outdated_mods = []
        all_incompatible_mods = {}

        if self.log.has_content("(Session ID is token:") and not self.log.has_content("(Session ID is token:<"):
            builder.error("leaked_session_id_token")
        
        match = re.search(r"/(Users|home)/([^/]+)/", self.log._content)
        if match and match.group(2).lower() not in ["user", "admin", "********"]:
            builder.info("leaked_username")
        match = None

        for mod in self.log.mods:
            metadata = self.get_mod_metadata(mod)
            if not metadata is None:
                if is_mcsr_log:
                    mod_name = metadata["name"]

                    try:
                        for incompatible_mod in metadata["incompatible"]:
                            if all_incompatible_mods[mod_name] is None:
                                all_incompatible_mods[mod_name] = [incompatible_mod]
                            else:
                                all_incompatible_mods[mod_name].append(incompatible_mod)
                    except KeyError: pass

                    if mod_name.lower() in checked_mods and not mod_name.lower() == "optifabric":
                        builder.note("duplicate_mod", mod_name.lower())
                    else: checked_mods.append(mod_name.lower())

                    latest_version = self.get_latest_version(metadata)
                    
                    if not latest_version is None and not (latest_version["name"] == mod or latest_version["version"] in mod):
                        if all(not weird_mod in mod.lower() for weird_mod in self.assume_as_latest):
                            outdated_mods.append(["outdated_mod", mod_name, latest_version["page"]])
                            continue
                    elif latest_version is None: continue
            elif all(not weird_mod in mod.lower() for weird_mod in self.assume_as_legal): illegal_mods.append(mod)
        
        if len(illegal_mods) > 0: builder.note("amount_illegal_mods", len(illegal_mods), "s" if len(illegal_mods) > 1 else f" (`{illegal_mods[0]}`)")
        
        if len(outdated_mods) > 5:
            builder.error("amount_outdated_mods", len(outdated_mods)).add("update_mods")
        else:
            for outdated_mod in outdated_mods:
                builder.warning(outdated_mod[0], outdated_mod[1], outdated_mod[2])

        for key, value in all_incompatible_mods.items():
            for incompatible_mod in value:
                if self.log.has_mod(incompatible_mod):
                    builder.error("incompatible_mod", key, incompatible_mod)
        
        if not self.log.operating_system is None and self.log.operating_system == OperatingSystem.MACOS:
            if self.log.has_mod("sodium-1.16.1-v1") or self.log.has_mod("sodium-1.16.1-v2"):
                builder.error("not_using_mac_sodium")
        
        if not self.log.major_java_version is None and self.log.major_java_version < 17 and not self.log.short_version == "1.12":
            wrong_mods = []
            for mod in self.java_17_mods:
                for installed_mod in self.log.mods:
                    if mod in installed_mod.lower():
                        wrong_mods.append(mod)
            if len(wrong_mods) > 0:
                builder.error(
                    "need_java_17_mods",
                    "mods" if len(wrong_mods) > 1 else
                    "a mod",
                    "`, `".join(wrong_mods),
                    "s" if len(wrong_mods) == 1 else
                    "",
                    f", but you're using `Java {self.log.major_java_version}`" if not self.log.major_java_version is None
                    else ""
                ).add("java_update_guide")
                found_crash_cause = True
        
        if not found_crash_cause and self.log.has_content("require the use of Java 17"):
            builder.error("need_java_17_mc").add("java_update_guide")
            found_crash_cause = True
        
        if not found_crash_cause:
            needed_java_version = None
            if self.log.has_content("java.lang.UnsupportedClassVersionError"):
                match = re.compile(r"class file version (\d+\.\d+)").search(self.log._content)
                if not match is None:
                    needed_java_version = round(float(match.group(1))) - 44
            compatibility_match = re.compile(r"The requested compatibility level (JAVA_\d+) could not be set.").search(self.log._content)
            if not compatibility_match is None:
                try:
                    parsed_version = int(compatibility_match.group(1).split("_")[1])
                    if needed_java_version is None or parsed_version > needed_java_version:
                        needed_java_version = parsed_version
                except: pass
            if not needed_java_version is None:
                builder.error("need_new_java", needed_java_version).add("java_update_guide")
                found_crash_cause = True
        
        if not found_crash_cause and any(self.log.has_content(crash_32_bit_java) for crash_32_bit_java in [
            "Could not reserve enough space for ",
            "Invalid maximum heap size: "
        ]):
            builder.error("32_bit_java_crash").add("java_update_guide")
            found_crash_cause = True
        
        if self.log.has_content("mcwrap.py"): pass
        
        elif not found_crash_cause and self.log.has_content("You might want to install a 64bit Java version"):
            if not self.log.operating_system is None and self.log.operating_system == OperatingSystem.MACOS:
                builder.error("arm_java_multimc").add("mac_setup_guide")
            else:
                builder.error("32_bit_java").add("java_update_guide")
            found_crash_cause = True

        elif not self.log.launcher is None and self.log.launcher.lower() == "multimc" and not self.log.operating_system is None and self.log.operating_system == OperatingSystem.MACOS:
            builder.note("use_prism").add("mac_setup_guide")
        
        if self.log.has_content("The java binary \"\" couldn't be found."):
            builder.error("no_java").add("java_update_guide")
            found_crash_cause = True
        
        if self.log.has_content("java.awt.AWTError: Assistive Technology not found: org.GNOME.Accessibility.AtkWrapper"):
            builder.error("headless_java")
            found_crash_cause = True

        if not found_crash_cause and (any(self.log.has_content(broken_java) for broken_java in [
            "Could not start java:\n\n\nCheck your MultiMC Java settings.",
            "Incompatible magic value 0 in class file sun/security/provider/SunEntries",
            "Assertion `version->filename == NULL || ! _dl_name_match_p (version->filename, map)' failed"
        ]) or not re.compile(r"The java binary \"(.+)\" couldn't be found.").search(self.log._content) is None):
            builder.error("broken_java").add("java_update_guide")
            found_crash_cause = True
        
        if any(self.log.has_content(new_java_old_fabric) for new_java_old_fabric in [
            "java.lang.IllegalArgumentException: Unsupported class file major version ",
            "java.lang.IllegalArgumentException: Class file major version "
        ]):
            mod_loader = self.log.mod_loader.value if self.log.mod_loader.value is not None else "mod"
            builder.error("new_java_old_fabric_crash", mod_loader, mod_loader)
            if self.log.short_version in [f"1.{14 + i}" for i in range(10)]: builder.add("fabric_guide_prism" if self.log.is_prism else "fabric_guide_mmc", "update")
            found_crash_cause = True
        elif not self.log.mod_loader is None and self.log.mod_loader == ModLoader.FABRIC and not self.log.fabric_version is None:
            highest_srigt_ver = None
            for mod in self.log.mods:
                if "speedrunigt" in mod.lower():
                    match = re.compile(r"-(\d+(?:\.\d+)?)\+").search(mod)
                    if not match is None:
                        try: ver = version.parse(match.group(1))
                        except: pass
                        if highest_srigt_ver is None or ver > highest_srigt_ver:
                            highest_srigt_ver = ver
            if not highest_srigt_ver is None:
                try:
                    if highest_srigt_ver < version.parse("13.3") and self.log.fabric_version > version.parse("0.14.14"):
                        builder.error("incompatible_srigt")
                        if not self.log.minecraft_version == "1.16.1":
                            builder.add("incompatible_srigt_alternative")
                        found_crash_cause = True
                except: pass
            
            if self.log.has_content("java.lang.ClassNotFoundException: can't find class com.llamalad7.mixinextras.MixinExtrasBootstrap"):
                builder.error("old_fabric_crash").add("fabric_guide_prism" if self.log.is_prism else "fabric_guide_mmc", "update")
                found_crash_cause = True
            
            else:
                try:
                    if self.log.fabric_version < version.parse("0.13.3"):
                        builder.error("really_old_fabric")
                        if self.log.short_version in [f"1.{14 + i}" for i in range(10)]: builder.add("fabric_guide_prism" if self.log.is_prism else "fabric_guide_mmc", "update")
                    elif self.log.fabric_version < version.parse("0.14.12"):
                        builder.warning("relatively_old_fabric")
                        if self.log.short_version in [f"1.{14 + i}" for i in range(10)]: builder.add("fabric_guide_prism" if self.log.is_prism else "fabric_guide_mmc", "update")
                    elif self.log.fabric_version < version.parse("0.14.14"):
                        builder.note("old_fabric").add("fabric_guide_prism" if self.log.is_prism else "fabric_guide_mmc", "update")
                    elif self.log.fabric_version.__str__() in ["0.14.15", "0.14.16"]:
                        builder.error("broken_fabric")
                        if self.log.short_version in [f"1.{14 + i}" for i in range(10)]: builder.add("fabric_guide_prism" if self.log.is_prism else "fabric_guide_mmc", "update")
                except: pass
        
        if not self.log.mod_loader in [None, ModLoader.FABRIC, ModLoader.VANILLA]:
            if is_mcsr_log:
                builder.error("using_other_loader_mcsr", self.log.mod_loader.value)
                if self.log.short_version in [f"1.{14 + i}" for i in range(10)]: builder.add("fabric_guide_prism" if self.log.is_prism else "fabric_guide_mmc", "install")
                found_crash_cause = True
            else:
                builder.note("using_other_loader", self.log.mod_loader.value)

        if len(self.log.mods) > 0 and self.log.mod_loader == ModLoader.VANILLA:
            builder.error("no_loader")
            if self.log.short_version in [f"1.{14 + i}" for i in range(10)]: builder.add("fabric_guide_prism" if self.log.is_prism else "fabric_guide_mmc", "install")
        
        if not found_crash_cause:
            has_fabric_mod = any(self.log.has_mod(mcsr_mod) for mcsr_mod in self.mcsr_mods) or self.log.has_mod("fabric")
            has_quilt_mod = self.log.has_mod("quilt")
            has_forge_mod = self.log.has_mod("forge")
            
            if has_forge_mod and not has_quilt_mod and not has_fabric_mod:
                if self.log.mod_loader == ModLoader.FABRIC:
                    builder.error("rong_modloader", "Forge", "Fabric")
                    found_crash_cause = True
                elif self.log.mod_loader == ModLoader.QUILT:
                    builder.error("rong_modloader", "Forge", "Quilt")
                    found_crash_cause = True
            elif has_fabric_mod and not has_forge_mod and self.log.mod_loader == ModLoader.FORGE:
                builder.error("rong_modloader", "Fabric", "Forge")
                found_crash_cause = True
            elif has_quilt_mod and not has_forge_mod and self.log.mod_loader == ModLoader.FORGE:
                builder.error("rong_modloader", "Quilt", "Forge")
                found_crash_cause = True
        
        if not self.log.max_allocated is None:
            has_shenandoah = self.log.has_java_argument("shenandoah")
            min_limit_1 = 1200 if has_shenandoah else 1900
            min_limit_2 = 850 if has_shenandoah else 1200
            ram_guide = "allocate_ram_guide_mmc" if self.log.is_multimc_or_fork else "allocate_ram_guide"
            if (self.log.max_allocated < min_limit_1 and self.log.has_content(" -805306369")) or self.log.has_content("OutOfMemoryError") or self.log.has_content("GL error GL_OUT_OF_MEMORY"):
                builder.error("too_little_ram_crash").add(ram_guide)
                found_crash_cause = True
            elif self.log.max_allocated < min_limit_2:
                builder.warning("too_little_ram").add(ram_guide)
            elif self.log.max_allocated < min_limit_1:
                builder.note("too_little_ram").add(ram_guide)
            if is_mcsr_log and not self.log.short_version in [f"1.{18 + i}" for i in range(10)]:
                if self.log.max_allocated > 10000:
                    builder.error("too_much_ram").add(ram_guide)
                elif self.log.max_allocated > 4800:
                    builder.warning("too_much_ram").add(ram_guide)
                elif self.log.max_allocated > 3500:
                    builder.note("too_much_ram").add(ram_guide)
        elif self.log.has_content("OutOfMemoryError") or self.log.has_content("GL error GL_OUT_OF_MEMORY"):
            ram_guide = "allocate_ram_guide_mmc" if self.log.is_multimc_or_fork else "allocate_ram_guide"
            builder.error("too_little_ram_crash").add(ram_guide)
        
        if not self.log.minecraft_folder is None:
            if "OneDrive" in self.log.minecraft_folder:
                builder.note("onedrive")
            if "C:/Program Files" in self.log.minecraft_folder:
                builder.note("program_files")
            if "Rar$" in self.log.minecraft_folder:
                builder.error("need_to_extract_from_zip",self.log.launcher if not self.log.launcher is None else "the launcher")
        
        if self.log.has_mod("phosphor") and not self.log.minecraft_version == "1.12.2":
            builder.note("starlight_better")
            metadata = self.get_mod_metadata("starlight")
            if not metadata is None:
                latest_version = self.get_latest_version(metadata)
                if not latest_version is None:
                    builder.add("mod_download", metadata["name"], latest_version["page"])
        
        if self.log.has_content("Failed to download the assets index"):
            builder.error("assets_index_fail")
        
        if self.log.has_content("Invalid id 4096 - maximum id range exceeded"):
            builder.error("exceeded_id_limit")
        
        if self.log.has_content("NSWindow drag regions should only be invalidated on the Main Thread"):
            builder.error("mac_too_new_java")
        
        if self.log.has_content("Pixel format not accelerated") or not re.compile(r"C  \[(ig[0-9]+icd[0-9]+\.dll)[+ ](0x[0-9a-f]+)\]").search(self.log._content) is None:
            if self.log.has_mod("speedrunigt"):
                builder.error("eav_crash").add("eav_crash_srigt")
            else:
                builder.error("gl_pixel_format")
        
        elif self.log.has_content("A fatal error has been detected by the Java Runtime Environment") or self.log.has_content("EXCEPTION_ACCESS_VIOLATION"):
            builder.error("eav_crash")
            for i in range(5): builder.add(f"eav_crash_{i + 1}")
            if self.log.has_mod("speedrunigt"): builder.add("eav_crash_srigt")
            builder.add("eav_crash_disclaimer")
        
        if self.log.has_content("WGL_ARB_create_context_profile is unavailable"):
            builder.error("intel_hd2000").add("intell_hd2000_info")

        if self.log.has_content("org.lwjgl.LWJGLException: Could not choose GLX13 config") or self.log.has_content("GLFW error 65545: GLX: Failed to find a suitable GLXFBConfig"):
            builder.error("outdated_nvidia_flatpack_driver")
        
        if self.log.has_content("java.lang.NoSuchMethodError: sun.security.util.ManifestEntryVerifier.<init>(Ljava/util/jar/Manifest;)V"):
            builder.error("forge_java_bug")
            found_crash_cause = True
        
        if self.log.has_content("java.lang.IllegalStateException: GLFW error before init: [0x10008]Cocoa: Failed to find service port for display"):
            builder.error("incompatible_forge_mac")
            found_crash_cause = True
        
        system_libs = [lib for lib in ["GLFW", "OpenAL"] if self.log.has_content("Using system " + lib)]
        system_arg = None
        if len(system_libs) == 2: system_arg = f"{system_libs[0]} and {system_libs[1]} installations"
        elif len(system_libs) == 1: system_arg = f"{system_libs[0]} installation"
        if not system_arg is None:
            if self.log.has_content("Failed to locate library:"):
                builder.error("builtin_lib_crash",
                              system_arg,
                              self.log.launcher if self.log.launcher is not None else "your launcher",
                              " > Tweaks" if self.log.is_prism else "")
                found_crash_cause = True
            else: builder.note("builtin_lib_recommendation", system_arg)

        required_mod_match = re.findall(r"requires (.*?) of (\w+),", self.log._content)
        for required_mod in required_mod_match:
            mod_name = required_mod[1]
            if mod_name.lower() == "fabric": builder.error("requires_fabric_api")
            else: builder.error("requires_mod", mod_name)
        
        if self.log.has_mod("fabric-api") and is_mcsr_log:
            builder.warning("using_fabric_api")
        
        if self.log.has_content("Couldn't extract native jar"):
            builder.error("locked_libs")
        
        if not re.compile(r"java\.io\.IOException: Directory \'(.+?)\' could not be created").search(self.log._content) is None:
            builder.error("try_admin_launch")
        
        if self.log.has_content("java.lang.NullPointerException: Cannot invoke \"net.minecraft.class_2680.method_26213()\" because \"state\" is null"):
            builder.error("old_sodium_crash")
            metadata = self.get_mod_metadata("sodium")
            if not metadata is None:
                latest_version = self.get_latest_version(metadata)
                if not latest_version is None:
                    builder.add("mod_download", metadata["name"], latest_version["page"])
            found_crash_cause = True
        elif self.log.has_content("me.jellysquid.mods.sodium.client.SodiumClientMod.options"):
            builder.error("sodium_config_crash")
            found_crash_cause = True
        
        pattern = r"Uncaught exception in thread \"Thread-\d+\"\njava\.util\.ConcurrentModificationException: null"
        if "java.util.ConcurrentModificationException" in re.sub(pattern, "", self.log._content) and not self.log.minecraft_version is None and self.log.short_version == "1.16" and not self.log.has_mod("voyager"):
            builder.error("no_voyager_crash")
        
        if self.log.has_content("java.lang.IllegalStateException: Adding Entity listener a second time") and self.log.has_content("me.jellysquid.mods.lithium.common.entity.tracker.nearby"):
            builder.info("lithium_crash")
            found_crash_cause = True
        
        if is_mcsr_log and any(self.log.has_content(log_spam) for log_spam in [
            "Using missing texture, unable to load",
            "Exception loading blockstate definition",
            "Unable to load model",
            "java.lang.NullPointerException: Cannot invoke \"com.mojang.authlib.minecraft.MinecraftProfileTexture.getHash()\" because \"?\" is null",
            " to profiler if profiler tick hasn't started - missing "
        ]): builder.info("log_spam")
        
        if self.log.has_mod("serversiderng-9"):
            builder.warning("using_ssrng")
        
        if any(self.log.has_mod(f"serversiderng-{i}") for i in range(1, 9)):
            builder.error("using_old_ssrng")
        elif self.log.has_content("Failed to light chunk") and self.log.has_content("net.minecraft.class_148: Feature placement") and self.log.has_content("java.lang.ArrayIndexOutOfBoundsException"):
            builder.info("starlight_crash")
        elif not found_crash_cause and self.log.has_content(" -805306369") or self.log.has_content("java.lang.ArithmeticException"):
            builder.warning("exitcode_805306369")

        if self.log.has_content(" -1073741819") or self.log.has_content("The instruction at 0x%p referenced memory at 0x%p. The memory could not be %s."):
            builder.error("exitcode", "-1073741819")
            builder.add("exitcode_1073741819_1").add("exitcode_1073741819_2")
            if self.log._content.count("\n") < 500:
                if self.log.has_mod("sodium") and not self.log.has_mod("sodiummac"): builder.add(f"exitcode_1073741819_3")
                builder.add(f"exitcode_1073741819_4")
            builder.add("exitcode_1073741819_5")

        if self.log.has_content(" -1073740791"):
            builder.error("exitcode", "-1073740791")
            builder.add("exitcode_1073741819_2")
            if self.log._content.count("\n") < 500: builder.add("exitcode_1073741819_4")
            builder.add("exitcode_1073741819_5")
        
        if self.log.has_mod("autoreset") or self.log.has_content("the mods atum and autoreset"):
            builder.error("autoreset_user")
            metadata = self.get_mod_metadata("atum")
            if not metadata is None:
                latest_version = self.get_latest_version(metadata)
                if not latest_version is None:
                    builder.add("mod_download", metadata["name"], latest_version["page"])
            found_crash_cause = True

        if self.log.has_content("Launched instance in offline mode") and self.log.has_content("(missing)\n"):
            builder.error("online_launch_required", "" if self.log.is_prism else " Instance")
            found_crash_cause = True
        
        pattern = r"This instance is not compatible with Java version (\d+)\.\nPlease switch to one of the following Java versions for this instance:\nJava version (\d+)"
        match = re.search(pattern, self.log._content)
        if not match is None:
            switch_java = False
            if self.log.short_version in [f"1.{17 + i}" for i in range(10)]:
                try:
                    current_version = int(match.group(1))
                    switch_java = (current_version < 17)
                except: switch_java = True
            elif self.log.mod_loader == ModLoader.FORGE: switch_java = True
            if switch_java:
                current_version = match.group(1)
                compatible_version = match.group(2)
                builder.error(
                    "incorrect_java_prism",
                    current_version,
                    compatible_version,
                    compatible_version,
                    " (download the .msi file)" if self.log.operating_system == OperatingSystem.WINDOWS else
                    " (download the .pkg file)" if self.log.operating_system == OperatingSystem.MACOS else
                    "",
                    compatible_version
                )
            else: builder.error("java_comp_check")
        
        if self.log.has_content("java.lang.ClassNotFoundException: org.apache.logging.log4j.spi.AbstractLogger"):
            builder.error("no_abstract_logger")
        
        if self.log.has_content("ClassLoaders$AppClassLoader cannot be cast to class java.net.URLClassLoader"):
            builder.error("forge_too_new_java")
            found_crash_cause = True
        if not self.log.mod_loader is None and self.log.mod_loader == ModLoader.FORGE and not found_crash_cause:
            if self.log.has_content("Unable to detect the forge installer!"):
                builder.error("random_forge_crash_1")
            if self.log.has_content("java.lang.NoClassDefFoundError: cpw/mods/modlauncher/Launcher"):
                builder.error("random_forge_crash_2")
        
        match = re.search(r"Incompatible mod set found! READ THE BELOW LINES!(.*?)(?=at com\.mcsr\.projectelo\.anticheat)", self.log._content, re.DOTALL)
        if match:
            found_crash_cause = True
            ranked_rong_files = []
            ranked_rong_mods = []
            ranked_rong_versions = []
            ranked_anticheat = match.group(1).strip().replace("\t","")
            ranked_anticheat_split = ranked_anticheat.split("These Fabric Mods are whitelisted but different version! Make sure to update these!")
            if len(ranked_anticheat_split) > 1:
                ranked_anticheat, ranked_anticheat_split = ranked_anticheat_split[0], ranked_anticheat_split[1].split("\n")
                for mod in ranked_anticheat_split:
                    match = re.search(r"\[(.*?)\]", mod)
                    if match:
                        ranked_rong_versions.append(match.group(1))
            ranked_anticheat_split = ranked_anticheat.split("These Fabric Mods are whitelisted and you seem to be using the correct version but the files do not match. Try downloading these files again!")
            if len(ranked_anticheat_split) > 1:
                ranked_anticheat, ranked_anticheat_split = ranked_anticheat_split[0], ranked_anticheat_split[1].split("\n")
                for mod in ranked_anticheat_split:
                    match = re.search(r"\[(.*?)\]", mod)
                    if match:
                        ranked_rong_files.append(match.group(1))
            ranked_anticheat_split = ranked_anticheat.split("These Fabric Mods are not whitelisted! You should delete these from Minecraft.")
            if len(ranked_anticheat_split) > 1:
                ranked_anticheat, ranked_anticheat_split = ranked_anticheat_split[0], ranked_anticheat_split[1].split("\n")
                for mod in ranked_anticheat_split:
                    match = re.search(r"\[(.*?)\]", mod)
                    if match:
                        match = match.group(1)
                        ranked_rong_mods.append("Fabric API" if match == "fabric" else match)

            if len(ranked_rong_versions) > 5:
                builder.error("ranked_rong_versions", f"`{len(ranked_rong_versions)}` mods (`{ranked_rong_versions[0]}, {ranked_rong_versions[1]}, ...`) that are", "them").add("update_mods_ranked")
            elif len(ranked_rong_versions) > 1:
                builder.error("ranked_rong_versions", f"`{len(ranked_rong_versions)}` mods (`{', '.join(ranked_rong_versions)}`) that are", "them").add("update_mods_ranked")
            elif len(ranked_rong_versions) > 0:
                builder.error("ranked_rong_versions", f"a mod `{ranked_rong_versions[0]}` that is", "it").add("update_mods_ranked")

            if len(ranked_rong_files) > 5:
                builder.error("ranked_rong_files", f"`{len(ranked_rong_files)}` mods (`{ranked_rong_files[0]}, {ranked_rong_files[1]}, ...`) that seem", "them").add("update_mods_ranked")
            elif len(ranked_rong_files) > 1:
                builder.error("ranked_rong_files", f"`{len(ranked_rong_files)}` mods (`{', '.join(ranked_rong_files)}`) that seem", "them").add("update_mods_ranked")
            elif len(ranked_rong_files) > 0:
                builder.error("ranked_rong_files", f"a mod `{ranked_rong_files[0]}` that seems", "it").add("update_mods_ranked")

            if len(ranked_rong_mods) > 5:
                builder.error("ranked_rong_mods", f"`{len(ranked_rong_mods)}` mods (`{ranked_rong_mods[0]}, {ranked_rong_mods[1]}, ...`) that are", "them")
            elif len(ranked_rong_mods) > 1:
                builder.error("ranked_rong_mods", f"`{len(ranked_rong_mods)}` mods (`{', '.join(ranked_rong_mods)}`) that are", "them")
            elif len(ranked_rong_mods) > 0:
                builder.error("ranked_rong_mods", f"a mod `{ranked_rong_mods[0]}` that is", "it")

        if self.log.has_content("com.mcsr.projectelo.anticheat.file.verifiers.ResourcePackVerifier"):
            builder.error("ranked_resourcepack_crash")
            found_crash_cause = True
        
        if self.log.has_mod("optifine"):
            if self.log.has_mod("worldpreview"):
                builder.error("incompatible_mod", "Optifine", "WorldPreview")
                found_crash_cause = True
            if self.log.has_mod("z-buffer-fog") and self.log.short_version in [f"1.{14 + i}" for i in range(10)]:
                builder.error("incompatible_mod", "Optifine", "z-buffer-fog")
                found_crash_cause = True
        
        if self.log.has_mod("esimod"):
            for incompatible_mod in ["serverSideRNG", "SpeedRunIGT", "WorldPreview", "mcsrranked"]:
                if self.log.has_mod(incompatible_mod):
                    builder.error("incompatible_mod", "esimod", incompatible_mod)

        if self.log.has_content("Mixin apply for mod areessgee failed areessgee.mixins.json:nether.StructureFeatureMixin from mod areessgee -> net.minecraft.class_3195"):
            builder.error("incompatible_mod", "AreEssGee", "peepoPractice")
            found_crash_cause = True
        
        if self.log.has_mod("speedrunigt") and self.log.has_mod("stronghold-trainer"):
            builder.error("incompatible_mod", "SpeedRunIGT", "Stronghold Trainer")
            found_crash_cause = True
        
        if self.log.has_mod("continuity") and self.log.has_mod("sodium") and not self.log.has_mod("indium"):
            builder.error("missing_dependency", "continuity", "indium")
            found_crash_cause = True
        
        if self.log.has_mod("worldpreview") and self.log.has_mod("carpet"):
            builder.error("incompatible_mod", "WorldPreview", "carpet")
            found_crash_cause = True

        if not found_crash_cause and self.log.has_content("Failed to store chunk") or self.log.has_content("There is not enough space on the disk"):
            builder.error("out_of_disk_space")
        
        if self.log.has_content("Mappings not present!"):
            if not self.log.short_version in [f"1.{14 + i}" for i in range(15)] and self.log.mod_loader == ModLoader.FABRIC:
                builder.error("legacy_fabric_modpack")
                found_crash_cause = True
            else:
                builder.warning("no_mappings", "" if self.log.is_prism else " Instance")

        if not found_crash_cause and self.log.has_content("ERROR]: Mixin apply for mod fabric-networking-api-v1 failed"):
            builder.error("delete_dot_fabric")

        wrong_mods = []
        if not found_crash_cause:
            for pattern in [
                r"ERROR]: Mixin apply for mod ([\w\-+]+) failed",
                r"from mod ([\w\-+]+) failed injection check",
                r"due to errors, provided by '([\w\-+]+)'"
            ]:
                match = re.search(pattern, self.log._content)
                if match:
                    mod_name = match.group(1)
                    wrong_mod = [mod for mod in self.log.mods if mod_name.lower() in mod.lower()]
                    if len(wrong_mod) > 0: wrong_mods += wrong_mod
                    else: wrong_mods.append(mod_name)
        
            match = re.search(r"Minecraft has crashed!.*|Failed to start Minecraft:.*|Unable to launch\n.*|Exception caught from launcher\n.*|---- Minecraft Crash Report ----.*A detailed walkthrough of the error", self.log._content, re.DOTALL)
            if not match is None:
                stacktrace = match.group().lower()
                if not "this is not a error" in stacktrace:
                    if len(self.log.mods) == 0:
                        for mcsr_mod in self.mcsr_mods:
                            if mcsr_mod.replace("-", "").lower() in stacktrace and not mcsr_mod in wrong_mods and not mcsr_mod.lower() in wrong_mods:
                                wrong_mods.append(mcsr_mod)
                    else:
                        for mod in self.log.mods:
                            mod_name = mod.lower().replace(".jar", "")
                            for c in ["+", "-", "_", "=", ",", " "]: mod_name = mod_name.replace(c, "-")
                            mod_name_parts = mod_name.split("-")
                            mod_name = ""
                            for part in mod_name_parts:
                                part0 = part
                                for c in [".", "fabric", "forge", "quilt", "v", "mc", "mod", "backport", "snapshot", "build", "prism"]: part = part.replace(c, "")
                                for c in range(10): part = part.replace(str(c), "")
                                if part == "": break
                                elif len(part) > 1: mod_name += part0
                            if len(mod_name) > 2 and mod_name in stacktrace:
                                if not mod in wrong_mods: wrong_mods.append(mod)
            if len(wrong_mods) == 1:
                builder.error("mod_crash", wrong_mods[0])
            elif len(wrong_mods) > 0 and len(wrong_mods) < 6:
                builder.error("mods_crash", "; ".join(wrong_mods))
        
        return builder
