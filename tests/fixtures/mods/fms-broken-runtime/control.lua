script.on_nth_tick(1, function()
  assert(prototypes.item["fms-does-not-exist"] ~= nil, "expected fms-does-not-exist to be a prototype")
end)
