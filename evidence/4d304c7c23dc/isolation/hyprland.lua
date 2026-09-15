hl.monitor({output="",mode="1280x800@60",position="auto",scale=1})
hl.config({
    xwayland={enabled=false},
    general={layout="dwindle",gaps_in=0,gaps_out=0,border_size=0},
    decoration={rounding=0,blur={enabled=false},shadow={enabled=false}},
    animations={enabled=false},
    misc={disable_hyprland_logo=true,disable_splash_rendering=true},
    ecosystem={no_update_news=true,no_donation_nag=true,enforce_permissions=false},
    cursor={no_hardware_cursors=1}
})
hl.window_rule({name="kittyscape-private-fixtures",match={class="kittyscape-qualification"},
    workspace="15 silent",tile=true})
