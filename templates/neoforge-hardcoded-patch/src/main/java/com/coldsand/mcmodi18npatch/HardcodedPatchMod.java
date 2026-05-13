package com.coldsand.mcmodi18npatch;

import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;

@Mod(HardcodedPatchMod.MOD_ID)
public final class HardcodedPatchMod {
    public static final String MOD_ID = "mc_mod_i18n_hardcoded_patch";

    public HardcodedPatchMod(IEventBus modEventBus) {
        HardcodedTranslations translations = HardcodedTranslations.load();
        NeoForge.EVENT_BUS.addListener(new ClientTooltipTranslator(translations)::onTooltip);
    }
}
