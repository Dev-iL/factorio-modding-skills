-- Test hooks report through the log: "[FMS-TEST] PASS <name>" or "[FMS-TEST] FAIL <name>: <why>".
local function check(name, ok, why)
  log("[FMS-TEST] " .. (ok and "PASS " or "FAIL ") .. name .. (ok and "" or (": " .. why)))
end

script.on_init(function()
  check("item prototype exists at map creation", prototypes.item["fms-test-item"] ~= nil, "prototype missing")
end)

script.on_nth_tick(1, function()
  check("item prototype exists while ticking", prototypes.item["fms-test-item"] ~= nil, "prototype missing")
  script.on_nth_tick(1, nil)
end)
