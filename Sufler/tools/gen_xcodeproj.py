#!/usr/bin/env python3
"""Regenerates Sufler.xcodeproj/project.pbxproj from the files on disk.

Run it after adding, removing or renaming source files:

    python3 Sufler/tools/gen_xcodeproj.py

The script is deterministic: object identifiers are derived from file paths,
so re-running it without changes produces an identical project file.
"""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # .../Sufler
PROJECT_DIR = ROOT / "Sufler.xcodeproj"
APP_NAME = "Sufler"
TEST_NAME = "SuflerTests"
BUNDLE_ID = "com.blip5895516.sufler"
DEPLOYMENT_TARGET = "16.0"
MARKETING_VERSION = "1.0"
BUILD_NUMBER = "1"

FILE_TYPES = {
    ".swift": "sourcecode.swift",
    ".plist": "text.plist.xml",
    ".xcassets": "folder.assetcatalog",
    ".md": "net.daringfireball.markdown",
    ".txt": "text",
}
SOURCE_EXT = {".swift"}
RESOURCE_EXT = {".xcassets"}
IGNORED = {".DS_Store"}


def uid(*parts: str) -> str:
    return hashlib.md5("/".join(parts).encode("utf-8")).hexdigest()[:24].upper()


def q(value) -> str:
    """Quote a value for the old-style plist format when needed."""
    s = str(value)
    if s and re.fullmatch(r"[A-Za-z0-9_./]+", s):
        return s
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


class Node:
    """A file or a group in the project navigator."""

    def __init__(self, path: Path, rel: str):
        self.path = path
        self.rel = rel                      # path relative to ROOT, used for ids
        self.is_group = path.is_dir() and path.suffix not in RESOURCE_EXT
        self.ref = uid("ref", rel)
        self.children = []
        if self.is_group:
            entries = sorted(
                (p for p in path.iterdir() if p.name not in IGNORED),
                key=lambda p: (not (p.is_dir() and p.suffix not in RESOURCE_EXT), p.name.lower()),
            )
            self.children = [Node(p, f"{rel}/{p.name}") for p in entries]

    def files(self):
        if self.is_group:
            for child in self.children:
                yield from child.files()
        else:
            yield self


def build_settings_block(settings: dict, indent: str) -> str:
    lines = []
    for key in sorted(settings):
        value = settings[key]
        if isinstance(value, (list, tuple)):
            lines.append(f"{indent}{q(key)} = (")
            for item in value:
                lines.append(f"{indent}\t{q(item)},")
            lines.append(f"{indent});")
        else:
            lines.append(f"{indent}{q(key)} = {q(value)};")
    return "\n".join(lines)


def main() -> None:
    app_group = Node(ROOT / APP_NAME, APP_NAME)
    test_group = Node(ROOT / TEST_NAME, TEST_NAME)

    app_files = list(app_group.files())
    test_files = list(test_group.files())
    app_sources = [f for f in app_files if f.path.suffix in SOURCE_EXT]
    app_resources = [f for f in app_files if f.path.suffix in RESOURCE_EXT]
    test_sources = [f for f in test_files if f.path.suffix in SOURCE_EXT]

    project_id = uid("project")
    main_group_id = uid("group", "main")
    products_group_id = uid("group", "products")
    app_product_id = uid("product", "app")
    test_product_id = uid("product", "tests")
    app_target_id = uid("target", "app")
    test_target_id = uid("target", "tests")
    proxy_id = uid("proxy", "tests->app")
    dependency_id = uid("dependency", "tests->app")

    phases = {
        "app_sources": uid("phase", "app", "sources"),
        "app_frameworks": uid("phase", "app", "frameworks"),
        "app_resources": uid("phase", "app", "resources"),
        "test_sources": uid("phase", "tests", "sources"),
        "test_frameworks": uid("phase", "tests", "frameworks"),
        "test_resources": uid("phase", "tests", "resources"),
    }
    config_lists = {
        "project": uid("configlist", "project"),
        "app": uid("configlist", "app"),
        "tests": uid("configlist", "tests"),
    }
    configs = {
        (scope, name): uid("config", scope, name)
        for scope in ("project", "app", "tests")
        for name in ("Debug", "Release")
    }

    def build_file_id(target: str, node: Node) -> str:
        return uid("buildfile", target, node.rel)

    out = []
    w = out.append
    w("// !$*UTF8*$!")
    w("{")
    w("\tarchiveVersion = 1;")
    w("\tclasses = {")
    w("\t};")
    w("\tobjectVersion = 56;")
    w("\tobjects = {")
    w("")

    # ---- PBXBuildFile
    w("/* Begin PBXBuildFile section */")
    for target, nodes in (("app", app_sources + app_resources), ("tests", test_sources)):
        for node in nodes:
            w(f"\t\t{build_file_id(target, node)} /* {node.path.name} */ = "
              f"{{isa = PBXBuildFile; fileRef = {node.ref} /* {node.path.name} */; }};")
    w("/* End PBXBuildFile section */")
    w("")

    # ---- PBXContainerItemProxy
    w("/* Begin PBXContainerItemProxy section */")
    w(f"\t\t{proxy_id} /* PBXContainerItemProxy */ = {{")
    w("\t\t\tisa = PBXContainerItemProxy;")
    w(f"\t\t\tcontainerPortal = {project_id} /* Project object */;")
    w("\t\t\tproxyType = 1;")
    w(f"\t\t\tremoteGlobalIDString = {app_target_id};")
    w(f"\t\t\tremoteInfo = {APP_NAME};")
    w("\t\t};")
    w("/* End PBXContainerItemProxy section */")
    w("")

    # ---- PBXFileReference
    w("/* Begin PBXFileReference section */")
    w(f"\t\t{app_product_id} /* {APP_NAME}.app */ = {{isa = PBXFileReference; explicitFileType = wrapper.application; "
      f"includeInIndex = 0; path = {APP_NAME}.app; sourceTree = BUILT_PRODUCTS_DIR; }};")
    w(f"\t\t{test_product_id} /* {TEST_NAME}.xctest */ = {{isa = PBXFileReference; explicitFileType = wrapper.cfbundle; "
      f"includeInIndex = 0; path = {TEST_NAME}.xctest; sourceTree = BUILT_PRODUCTS_DIR; }};")
    for node in app_files + test_files:
        file_type = FILE_TYPES.get(node.path.suffix, "text")
        w(f"\t\t{node.ref} /* {node.path.name} */ = {{isa = PBXFileReference; lastKnownFileType = {file_type}; "
          f"path = {q(node.path.name)}; sourceTree = \"<group>\"; }};")
    w("/* End PBXFileReference section */")
    w("")

    # ---- PBXFrameworksBuildPhase
    w("/* Begin PBXFrameworksBuildPhase section */")
    for key in ("app_frameworks", "test_frameworks"):
        w(f"\t\t{phases[key]} /* Frameworks */ = {{")
        w("\t\t\tisa = PBXFrameworksBuildPhase;")
        w("\t\t\tbuildActionMask = 2147483647;")
        w("\t\t\tfiles = (")
        w("\t\t\t);")
        w("\t\t\trunOnlyForDeploymentPostprocessing = 0;")
        w("\t\t};")
    w("/* End PBXFrameworksBuildPhase section */")
    w("")

    # ---- PBXGroup
    w("/* Begin PBXGroup section */")
    w(f"\t\t{main_group_id} = {{")
    w("\t\t\tisa = PBXGroup;")
    w("\t\t\tchildren = (")
    w(f"\t\t\t\t{app_group.ref} /* {APP_NAME} */,")
    w(f"\t\t\t\t{test_group.ref} /* {TEST_NAME} */,")
    w(f"\t\t\t\t{products_group_id} /* Products */,")
    w("\t\t\t);")
    w("\t\t\tsourceTree = \"<group>\";")
    w("\t\t};")
    w(f"\t\t{products_group_id} /* Products */ = {{")
    w("\t\t\tisa = PBXGroup;")
    w("\t\t\tchildren = (")
    w(f"\t\t\t\t{app_product_id} /* {APP_NAME}.app */,")
    w(f"\t\t\t\t{test_product_id} /* {TEST_NAME}.xctest */,")
    w("\t\t\t);")
    w("\t\t\tname = Products;")
    w("\t\t\tsourceTree = \"<group>\";")
    w("\t\t};")

    def write_group(node: Node) -> None:
        w(f"\t\t{node.ref} /* {node.path.name} */ = {{")
        w("\t\t\tisa = PBXGroup;")
        w("\t\t\tchildren = (")
        for child in node.children:
            w(f"\t\t\t\t{child.ref} /* {child.path.name} */,")
        w("\t\t\t);")
        w(f"\t\t\tpath = {q(node.path.name)};")
        w("\t\t\tsourceTree = \"<group>\";")
        w("\t\t};")
        for child in node.children:
            if child.is_group:
                write_group(child)

    write_group(app_group)
    write_group(test_group)
    w("/* End PBXGroup section */")
    w("")

    # ---- PBXNativeTarget
    w("/* Begin PBXNativeTarget section */")
    w(f"\t\t{app_target_id} /* {APP_NAME} */ = {{")
    w("\t\t\tisa = PBXNativeTarget;")
    w(f"\t\t\tbuildConfigurationList = {config_lists['app']} /* Build configuration list for PBXNativeTarget \"{APP_NAME}\" */;")
    w("\t\t\tbuildPhases = (")
    w(f"\t\t\t\t{phases['app_sources']} /* Sources */,")
    w(f"\t\t\t\t{phases['app_frameworks']} /* Frameworks */,")
    w(f"\t\t\t\t{phases['app_resources']} /* Resources */,")
    w("\t\t\t);")
    w("\t\t\tbuildRules = (")
    w("\t\t\t);")
    w("\t\t\tdependencies = (")
    w("\t\t\t);")
    w(f"\t\t\tname = {APP_NAME};")
    w(f"\t\t\tproductName = {APP_NAME};")
    w(f"\t\t\tproductReference = {app_product_id} /* {APP_NAME}.app */;")
    w("\t\t\tproductType = \"com.apple.product-type.application\";")
    w("\t\t};")
    w(f"\t\t{test_target_id} /* {TEST_NAME} */ = {{")
    w("\t\t\tisa = PBXNativeTarget;")
    w(f"\t\t\tbuildConfigurationList = {config_lists['tests']} /* Build configuration list for PBXNativeTarget \"{TEST_NAME}\" */;")
    w("\t\t\tbuildPhases = (")
    w(f"\t\t\t\t{phases['test_sources']} /* Sources */,")
    w(f"\t\t\t\t{phases['test_frameworks']} /* Frameworks */,")
    w(f"\t\t\t\t{phases['test_resources']} /* Resources */,")
    w("\t\t\t);")
    w("\t\t\tbuildRules = (")
    w("\t\t\t);")
    w("\t\t\tdependencies = (")
    w(f"\t\t\t\t{dependency_id} /* PBXTargetDependency */,")
    w("\t\t\t);")
    w(f"\t\t\tname = {TEST_NAME};")
    w(f"\t\t\tproductName = {TEST_NAME};")
    w(f"\t\t\tproductReference = {test_product_id} /* {TEST_NAME}.xctest */;")
    w("\t\t\tproductType = \"com.apple.product-type.bundle.unit-test\";")
    w("\t\t};")
    w("/* End PBXNativeTarget section */")
    w("")

    # ---- PBXProject
    w("/* Begin PBXProject section */")
    w(f"\t\t{project_id} /* Project object */ = {{")
    w("\t\t\tisa = PBXProject;")
    w("\t\t\tattributes = {")
    w("\t\t\t\tBuildIndependentTargetsInParallel = 1;")
    w("\t\t\t\tLastSwiftUpdateCheck = 1500;")
    w("\t\t\t\tLastUpgradeCheck = 1500;")
    w("\t\t\t\tTargetAttributes = {")
    w(f"\t\t\t\t\t{app_target_id} = {{")
    w("\t\t\t\t\t\tCreatedOnToolsVersion = 15.0;")
    w("\t\t\t\t\t};")
    w(f"\t\t\t\t\t{test_target_id} = {{")
    w("\t\t\t\t\t\tCreatedOnToolsVersion = 15.0;")
    w(f"\t\t\t\t\t\tTestTargetID = {app_target_id};")
    w("\t\t\t\t\t};")
    w("\t\t\t\t};")
    w("\t\t\t};")
    w(f"\t\t\tbuildConfigurationList = {config_lists['project']} /* Build configuration list for PBXProject \"{APP_NAME}\" */;")
    w("\t\t\tcompatibilityVersion = \"Xcode 14.0\";")
    w("\t\t\tdevelopmentRegion = ru;")
    w("\t\t\thasScannedForEncodings = 0;")
    w("\t\t\tknownRegions = (")
    w("\t\t\t\tru,")
    w("\t\t\t\tBase,")
    w("\t\t\t);")
    w(f"\t\t\tmainGroup = {main_group_id};")
    w(f"\t\t\tproductRefGroup = {products_group_id} /* Products */;")
    w("\t\t\tprojectDirPath = \"\";")
    w("\t\t\tprojectRoot = \"\";")
    w("\t\t\ttargets = (")
    w(f"\t\t\t\t{app_target_id} /* {APP_NAME} */,")
    w(f"\t\t\t\t{test_target_id} /* {TEST_NAME} */,")
    w("\t\t\t);")
    w("\t\t};")
    w("/* End PBXProject section */")
    w("")

    # ---- PBXResourcesBuildPhase
    w("/* Begin PBXResourcesBuildPhase section */")
    for key, target, nodes in (("app_resources", "app", app_resources), ("test_resources", "tests", [])):
        w(f"\t\t{phases[key]} /* Resources */ = {{")
        w("\t\t\tisa = PBXResourcesBuildPhase;")
        w("\t\t\tbuildActionMask = 2147483647;")
        w("\t\t\tfiles = (")
        for node in nodes:
            w(f"\t\t\t\t{build_file_id(target, node)} /* {node.path.name} */,")
        w("\t\t\t);")
        w("\t\t\trunOnlyForDeploymentPostprocessing = 0;")
        w("\t\t};")
    w("/* End PBXResourcesBuildPhase section */")
    w("")

    # ---- PBXSourcesBuildPhase
    w("/* Begin PBXSourcesBuildPhase section */")
    for key, target, nodes in (("app_sources", "app", app_sources), ("test_sources", "tests", test_sources)):
        w(f"\t\t{phases[key]} /* Sources */ = {{")
        w("\t\t\tisa = PBXSourcesBuildPhase;")
        w("\t\t\tbuildActionMask = 2147483647;")
        w("\t\t\tfiles = (")
        for node in nodes:
            w(f"\t\t\t\t{build_file_id(target, node)} /* {node.path.name} */,")
        w("\t\t\t);")
        w("\t\t\trunOnlyForDeploymentPostprocessing = 0;")
        w("\t\t};")
    w("/* End PBXSourcesBuildPhase section */")
    w("")

    # ---- PBXTargetDependency
    w("/* Begin PBXTargetDependency section */")
    w(f"\t\t{dependency_id} /* PBXTargetDependency */ = {{")
    w("\t\t\tisa = PBXTargetDependency;")
    w(f"\t\t\ttarget = {app_target_id} /* {APP_NAME} */;")
    w(f"\t\t\ttargetProxy = {proxy_id} /* PBXContainerItemProxy */;")
    w("\t\t};")
    w("/* End PBXTargetDependency section */")
    w("")

    # ---- XCBuildConfiguration
    common = {
        "ALWAYS_SEARCH_USER_PATHS": "NO",
        "ASSETCATALOG_COMPILER_GENERATE_SWIFT_ASSET_SYMBOL_EXTENSIONS": "YES",
        "CLANG_ANALYZER_NONNULL": "YES",
        "CLANG_ANALYZER_NUMBER_OBJECT_CONVERSION": "YES_AGGRESSIVE",
        "CLANG_CXX_LANGUAGE_STANDARD": "gnu++20",
        "CLANG_ENABLE_MODULES": "YES",
        "CLANG_ENABLE_OBJC_ARC": "YES",
        "CLANG_ENABLE_OBJC_WEAK": "YES",
        "CLANG_WARN_BLOCK_CAPTURE_AUTORELEASING": "YES",
        "CLANG_WARN_BOOL_CONVERSION": "YES",
        "CLANG_WARN_COMMA": "YES",
        "CLANG_WARN_CONSTANT_CONVERSION": "YES",
        "CLANG_WARN_DEPRECATED_OBJC_IMPLEMENTATIONS": "YES",
        "CLANG_WARN_DIRECT_OBJC_ISA_USAGE": "YES_ERROR",
        "CLANG_WARN_DOCUMENTATION_COMMENTS": "YES",
        "CLANG_WARN_EMPTY_BODY": "YES",
        "CLANG_WARN_ENUM_CONVERSION": "YES",
        "CLANG_WARN_INFINITE_RECURSION": "YES",
        "CLANG_WARN_INT_CONVERSION": "YES",
        "CLANG_WARN_NON_LITERAL_NULL_CONVERSION": "YES",
        "CLANG_WARN_OBJC_IMPLICIT_RETAIN_SELF": "YES",
        "CLANG_WARN_OBJC_LITERAL_CONVERSION": "YES",
        "CLANG_WARN_OBJC_ROOT_CLASS": "YES_ERROR",
        "CLANG_WARN_QUOTED_INCLUDE_IN_FRAMEWORK_HEADER": "YES",
        "CLANG_WARN_RANGE_LOOP_ANALYSIS": "YES",
        "CLANG_WARN_STRICT_PROTOTYPES": "YES",
        "CLANG_WARN_SUSPICIOUS_MOVE": "YES",
        "CLANG_WARN_UNGUARDED_AVAILABILITY": "YES_AGGRESSIVE",
        "CLANG_WARN_UNREACHABLE_CODE": "YES",
        "CLANG_WARN__DUPLICATE_METHOD_MATCH": "YES",
        "COPY_PHASE_STRIP": "NO",
        "ENABLE_STRICT_OBJC_MSGSEND": "YES",
        "ENABLE_USER_SCRIPT_SANDBOXING": "YES",
        "GCC_C_LANGUAGE_STANDARD": "gnu17",
        "GCC_NO_COMMON_BLOCKS": "YES",
        "GCC_WARN_64_TO_32_BIT_CONVERSION": "YES",
        "GCC_WARN_ABOUT_RETURN_TYPE": "YES_ERROR",
        "GCC_WARN_UNDECLARED_SELECTOR": "YES",
        "GCC_WARN_UNINITIALIZED_AUTOS": "YES_AGGRESSIVE",
        "GCC_WARN_UNUSED_FUNCTION": "YES",
        "GCC_WARN_UNUSED_VARIABLE": "YES",
        "IPHONEOS_DEPLOYMENT_TARGET": DEPLOYMENT_TARGET,
        "LOCALIZATION_PREFERS_STRING_CATALOGS": "YES",
        "MTL_FAST_MATH": "YES",
        "SDKROOT": "iphoneos",
        "SWIFT_VERSION": "5.0",
    }
    project_debug = dict(common, **{
        "DEBUG_INFORMATION_FORMAT": "dwarf",
        "ENABLE_TESTABILITY": "YES",
        "GCC_DYNAMIC_NO_PIC": "NO",
        "GCC_OPTIMIZATION_LEVEL": "0",
        "GCC_PREPROCESSOR_DEFINITIONS": ["DEBUG=1", "$(inherited)"],
        "MTL_ENABLE_DEBUG_INFO": "INCLUDE_SOURCE",
        "ONLY_ACTIVE_ARCH": "YES",
        "SWIFT_ACTIVE_COMPILATION_CONDITIONS": "DEBUG $(inherited)",
        "SWIFT_OPTIMIZATION_LEVEL": "-Onone",
    })
    project_release = dict(common, **{
        "DEBUG_INFORMATION_FORMAT": "dwarf-with-dsym",
        "ENABLE_NS_ASSERTIONS": "NO",
        "MTL_ENABLE_DEBUG_INFO": "NO",
        "SWIFT_COMPILATION_MODE": "wholemodule",
        "VALIDATE_PRODUCT": "YES",
    })
    app_settings = {
        "ASSETCATALOG_COMPILER_APPICON_NAME": "AppIcon",
        "ASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME": "AccentColor",
        "CODE_SIGN_STYLE": "Automatic",
        "CURRENT_PROJECT_VERSION": BUILD_NUMBER,
        "ENABLE_PREVIEWS": "YES",
        "GENERATE_INFOPLIST_FILE": "NO",
        "INFOPLIST_FILE": f"{APP_NAME}/Info.plist",
        "LD_RUNPATH_SEARCH_PATHS": ["$(inherited)", "@executable_path/Frameworks"],
        "MARKETING_VERSION": MARKETING_VERSION,
        "PRODUCT_BUNDLE_IDENTIFIER": BUNDLE_ID,
        "PRODUCT_NAME": "$(TARGET_NAME)",
        "SUPPORTED_PLATFORMS": "iphoneos iphonesimulator",
        "SUPPORTS_MACCATALYST": "NO",
        "SUPPORTS_MAC_DESIGNED_FOR_IPHONE_IPAD": "NO",
        "SUPPORTS_XR_DESIGNED_FOR_IPHONE_IPAD": "NO",
        "SWIFT_EMIT_LOC_STRINGS": "YES",
        "TARGETED_DEVICE_FAMILY": "1",
    }
    test_settings = {
        "BUNDLE_LOADER": "$(TEST_HOST)",
        "CODE_SIGN_STYLE": "Automatic",
        "CURRENT_PROJECT_VERSION": BUILD_NUMBER,
        "GENERATE_INFOPLIST_FILE": "YES",
        "MARKETING_VERSION": MARKETING_VERSION,
        "PRODUCT_BUNDLE_IDENTIFIER": f"{BUNDLE_ID}.tests",
        "PRODUCT_NAME": "$(TARGET_NAME)",
        "SUPPORTED_PLATFORMS": "iphoneos iphonesimulator",
        "SWIFT_EMIT_LOC_STRINGS": "NO",
        "TARGETED_DEVICE_FAMILY": "1",
        "TEST_HOST": f"$(BUILT_PRODUCTS_DIR)/{APP_NAME}.app/$(BUNDLE_EXECUTABLE_FOLDER_PATH)/{APP_NAME}",
    }
    w("/* Begin XCBuildConfiguration section */")
    for scope, name, settings in (
        ("project", "Debug", project_debug),
        ("project", "Release", project_release),
        ("app", "Debug", app_settings),
        ("app", "Release", app_settings),
        ("tests", "Debug", test_settings),
        ("tests", "Release", test_settings),
    ):
        w(f"\t\t{configs[(scope, name)]} /* {name} */ = {{")
        w("\t\t\tisa = XCBuildConfiguration;")
        w("\t\t\tbuildSettings = {")
        w(build_settings_block(settings, "\t\t\t\t"))
        w("\t\t\t};")
        w(f"\t\t\tname = {name};")
        w("\t\t};")
    w("/* End XCBuildConfiguration section */")
    w("")

    # ---- XCConfigurationList
    w("/* Begin XCConfigurationList section */")
    for scope, label in (
        ("project", f"PBXProject \"{APP_NAME}\""),
        ("app", f"PBXNativeTarget \"{APP_NAME}\""),
        ("tests", f"PBXNativeTarget \"{TEST_NAME}\""),
    ):
        w(f"\t\t{config_lists[scope]} /* Build configuration list for {label} */ = {{")
        w("\t\t\tisa = XCConfigurationList;")
        w("\t\t\tbuildConfigurations = (")
        w(f"\t\t\t\t{configs[(scope, 'Debug')]} /* Debug */,")
        w(f"\t\t\t\t{configs[(scope, 'Release')]} /* Release */,")
        w("\t\t\t);")
        w("\t\t\tdefaultConfigurationIsVisible = 0;")
        w("\t\t\tdefaultConfigurationName = Release;")
        w("\t\t};")
    w("/* End XCConfigurationList section */")
    w("\t};")
    w(f"\trootObject = {project_id} /* Project object */;")
    w("}")
    w("")

    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    (PROJECT_DIR / "project.pbxproj").write_text("\n".join(out), encoding="utf-8")

    scheme_dir = PROJECT_DIR / "xcshareddata" / "xcschemes"
    scheme_dir.mkdir(parents=True, exist_ok=True)
    (scheme_dir / f"{APP_NAME}.xcscheme").write_text(scheme_xml(app_target_id, test_target_id), encoding="utf-8")

    print(f"project.pbxproj: {len(app_sources)} app sources, {len(app_resources)} resources, "
          f"{len(test_sources)} test sources")


def scheme_xml(app_target_id: str, test_target_id: str) -> str:
    def buildable(target_id: str, product: str, blueprint: str, indent: str) -> str:
        return (
            f"{indent}<BuildableReference\n"
            f"{indent}   BuildableIdentifier = \"primary\"\n"
            f"{indent}   BlueprintIdentifier = \"{target_id}\"\n"
            f"{indent}   BuildableName = \"{product}\"\n"
            f"{indent}   BlueprintName = \"{blueprint}\"\n"
            f"{indent}   ReferencedContainer = \"container:{APP_NAME}.xcodeproj\">\n"
            f"{indent}</BuildableReference>"
        )

    app_ref = lambda indent: buildable(app_target_id, f"{APP_NAME}.app", APP_NAME, indent)
    test_ref = lambda indent: buildable(test_target_id, f"{TEST_NAME}.xctest", TEST_NAME, indent)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Scheme
   LastUpgradeVersion = "1500"
   version = "1.7">
   <BuildAction
      parallelizeBuildables = "YES"
      buildImplicitDependencies = "YES">
      <BuildActionEntries>
         <BuildActionEntry
            buildForTesting = "YES"
            buildForRunning = "YES"
            buildForProfiling = "YES"
            buildForArchiving = "YES"
            buildForAnalyzing = "YES">
{app_ref("            ")}
         </BuildActionEntry>
      </BuildActionEntries>
   </BuildAction>
   <TestAction
      buildConfiguration = "Debug"
      selectedDebuggerIdentifier = "Xcode.DebuggerFoundation.Debugger.LLDB"
      selectedLauncherIdentifier = "Xcode.DebuggerFoundation.Launcher.LLDB"
      shouldUseLaunchSchemeArgsEnv = "YES"
      shouldAutocreateTestPlan = "YES">
      <Testables>
         <TestableReference
            skipped = "NO"
            parallelizable = "NO">
{test_ref("            ")}
         </TestableReference>
      </Testables>
   </TestAction>
   <LaunchAction
      buildConfiguration = "Release"
      selectedDebuggerIdentifier = "Xcode.DebuggerFoundation.Debugger.LLDB"
      selectedLauncherIdentifier = "Xcode.DebuggerFoundation.Launcher.LLDB"
      launchStyle = "0"
      useCustomWorkingDirectory = "NO"
      ignoresPersistentStateOnLaunch = "NO"
      debugDocumentVersioning = "YES"
      debugServiceExtension = "internal"
      allowLocationSimulation = "YES">
      <BuildableProductRunnable
         runnableDebuggingMode = "0">
{app_ref("         ")}
      </BuildableProductRunnable>
   </LaunchAction>
   <ProfileAction
      buildConfiguration = "Release"
      shouldUseLaunchSchemeArgsEnv = "YES"
      savedToolIdentifier = ""
      useCustomWorkingDirectory = "NO"
      debugDocumentVersioning = "YES">
      <BuildableProductRunnable
         runnableDebuggingMode = "0">
{app_ref("         ")}
      </BuildableProductRunnable>
   </ProfileAction>
   <AnalyzeAction
      buildConfiguration = "Debug">
   </AnalyzeAction>
   <ArchiveAction
      buildConfiguration = "Release"
      revealArchiveInOrganizer = "YES">
   </ArchiveAction>
</Scheme>
"""


if __name__ == "__main__":
    main()
