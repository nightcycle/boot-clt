import os
import sys
import toml
import multiprocessing
import luau.roblox.util as ro_util
import luau.path as luau_path
import luau.roblox as roblox
import luau.roblox.rojo as rojo
from luau import indent_block
from typing import TypedDict, Literal, Any

GENERATED_HEADER_COMMENT = "-- generated by nightcycle/boot-clt, do not manually edit"
CONFIG_PATH = "boot.toml"

INIT_TAG = "init"
BUILD_TAG = "build"

CONFIG_DATA_TEMPLATE = {
	"boot_order": [
		{
			"modules": [],
			"is_shared": True,
			"domain_path": "game/ReplicatedStorage/Packages",
			"build_path": None
		},
		{
			"modules": [],
			"is_shared": True,
			"domain_path": "game/ReplicatedStorage/Shared",
			"build_path": None
		},
		{
			"modules": [],
			"is_shared": False,
			"domain_path": "game/ServerScriptService/Server",
			"build_path": "src/Server/Boot.server.luau"
		},
		{
			"modules": [],
			"is_shared": False,
			"domain_path": "game/ReplicatedFirst/First",
			"build_path": "src/First/Boot.client.luau"
		},
		{
			"modules": [],
			"is_shared": False,
			"domain_path": "game/ReplicatedStorage/Client",
			"build_path": "src/Client/Boot.client.luau"
		},
	]
}

class BuildConfig(TypedDict):
	modules: list[str]
	is_shared: bool
	domain_path: str
	build_path: None | str

class ConfigData(TypedDict):
	boot_order: list[BuildConfig]


def get_package_zip_path() -> str:
	base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
	# print(base_path)
	# for sub_path in os.listdir(base_path):
	# 	print(sub_path)

	return os.path.join(base_path, "data\\Packages.zip")

def get_config_data() -> ConfigData:
	file = open(CONFIG_PATH, "r")
	untyped_data: Any = toml.loads(file.read())
	return untyped_data

def init():

	if os.path.exists(CONFIG_PATH):
		raise ValueError("boot clt is already initialized at boot.toml")
		
	file = open(CONFIG_PATH, "w")
	file.write(toml.dumps(CONFIG_DATA_TEMPLATE))
	file.close()

def boot_domain() -> None:
	rojo.get_rojo_project_path()
	assert os.path.exists("wally.toml"), "boot clt requires wally"
	assert os.path.exists("foreman.toml") or os.path.exists("aftman.toml"), "boot clt requires foreman or aftman"
	config_data: ConfigData = get_config_data()
	config_data_list = config_data["boot_order"]

	for i, current_build_config in enumerate(config_data_list):
		if "build_path" in current_build_config and current_build_config["build_path"] != None:
			builds: list[BuildConfig] = []
			if i > 0: 
				for pre_config in config_data_list[0:(i-1)]:
					if pre_config["is_shared"]:
						builds.append(pre_config)

			builds.append(current_build_config)

			contents = [
				"--!strict",
				GENERATED_HEADER_COMMENT,
				"-- Services",
				"-- Packages",
				"local Maid = " + roblox.get_package_require("Maid"),
				"type Maid = Maid.Maid",
			]

			def boot_module(module_name: str, path: str) -> str:
				return f"{ro_util.get_module_require(path)}.init(maid)" 
			
			block_contents = []
			for build_config in builds:
				for module_name in build_config["modules"]:
					block_contents.append(boot_module(module_name, build_config["domain_path"]+"/"+module_name))

			build_path = current_build_config["build_path"]
			luau_path.remove_all_path_variants(build_path, "client")
			luau_path.remove_all_path_variants(build_path, "server")
			luau_path.remove_all_path_variants(build_path)

			if luau_path.get_if_module_script(build_path):
				contents.append("return function(maid: Maid): nil")
				contents += indent_block(block_contents, indent_count=1)
				contents.append("\tmaid:GiveTask(script.Destroying:Connect(function() maid:Destroy() end))")
				contents.append("\treturn nil")
				contents.append("end")
			else:
				contents.append(f"local maid = Maid.new()")
				contents += block_contents
				contents.append("maid:GiveTask(script.Destroying:Connect(function() maid:Destroy() end))")

			roblox.write_script(build_path, "\n".join(contents), get_package_zip_path())

	return None

def main():
	assert len(sys.argv) > 1, "no argument provided"

	if sys.argv[1] == BUILD_TAG:
		boot_domain()
	elif sys.argv[1] == INIT_TAG:
		init()
	else:
		raise ValueError("not a known tag")

# prevent from running twice
if __name__ == '__main__':
	multiprocessing.freeze_support()
	main()		
