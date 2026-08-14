from souladapt import SoulAdapt
import os

print("🧬 Demo: SoulAdapt - adaptation & sincerity")

for db in ("demo_adapt.db", "demo_mem.db"):
    if os.path.exists(db):
        os.remove(db)

# ---- Standalone: learn how to treat the user ----
adapt = SoulAdapt("demo_adapt.db")
adapt.observe("Prefiere respuestas cortas y directas", category="style")
adapt.observe("Ruptura con Ana", category="sensitive")
adapt.observe("Le gustan los gatos y el gimnasio", category="interests")

d = adapt.decide("hola, ¿cómo vas?")
print("\n📋 Standalone decision:")
print(f"   style:     {d['style']}")
print(f"   avoid:     {d['avoid']}")
print(f"   interests: {d['interests']}")
print(f"   honesty:   {d['honesty']} (no memory connected)")
adapt.close()

# ---- Connected: sincerity calibrated by SoulMemory ----
from soulmemory import SoulMemory

mem = SoulMemory("demo_mem.db")
mem.remember("Hoy fui al gimnasio y entrené piernas")

adapt2 = SoulAdapt("demo_adapt.db", memory=mem)
d2 = adapt2.decide("¿qué sabes de mi entrenamiento?")
print("\n💎 Connected decision:")
print(f"   confidence: {d2['confidence']}")
print(f"   honesty:    {d2['honesty']}")
for m in d2["memories"]:
    print(f"   📌 {m['content']} ({m['honesty']})")
adapt2.close()
mem.close()

print("\n✨ SoulAdapt demo completed!")