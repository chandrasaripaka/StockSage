import sys
import pkgutil

# Find all top-level modules
print("Python sys.path:")
for path in sys.path:
    print(path)

print("\nLooking for tigeropen package...")
try:
    import tigeropen
    print("tigeropen package found!")
    print("tigeropen version:", tigeropen.__version__ if hasattr(tigeropen, "__version__") else "unknown")
    
    # Print all modules in tigeropen
    print("\nModules in tigeropen:")
    package = tigeropen
    for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
        print(f"- {modname} {'(package)' if ispkg else '(module)'}")
    
    # Print TigerOpenClientConfig attributes and constructor
    print("\nImporting TigerOpenClientConfig...")
    try:
        from tigeropen.tiger_open_config import TigerOpenClientConfig
        config = TigerOpenClientConfig
        print("TigerOpenClientConfig found!")
        print("Constructor signature:", str(config.__init__.__code__.co_varnames))
        print("Number of arguments:", config.__init__.__code__.co_argcount)
    except Exception as e:
        print("Error importing TigerOpenClientConfig:", str(e))
    
except ImportError:
    print("tigeropen package not found!")
    
print("\nDone.")