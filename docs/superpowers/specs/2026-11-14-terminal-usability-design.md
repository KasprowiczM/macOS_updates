# Terminal usability redesign

The owner's live feedback rejects the 1.8.0 interaction model. The implementation must expose actions as controls, preserve predictable navigation and show installed applications as data rather than transient command output. No real host application update, launch, quit or installation is authorized for this work.

## Approach

Keep the standard-library curses runtime and existing execution engine, replacing implicit pane shortcuts with a control-oriented model. A new widget framework would add a Python/bootstrap dependency without itself fixing consent and inventory semantics. The owner supplied the workflow and delegated implementation choices; the following are builder choices.

A persistent header identifies macOS Updates, version and Michał Kasprowicz. Left navigation contains grouped work areas; the center holds visible focusable controls and data; right help explains the current focus and next step. A fixed bottom action row presents Back/Next in the wizard, Save in settings, Preview/Run in updates, and Exit/Help consistently. Tab cycles controls, arrows move predictably, Space toggles only checkboxes, Enter activates the focused button. Disabled controls explain why. Input prompts open an editor automatically with question context and explicit Send/Cancel. No hidden i requirement.

Inventory reads the saved structured snapshot, groups by actual source, and supports search, sort and paging. Each row exposes source, version, policy and reason. Exclude records an ignore policy; re-enable removes the exclusion and requires a separate future consent decision, never resurrecting old grants. Exclusion does not uninstall an application or erase observation evidence. Unknown sources stay visible. A manual capability explains the missing accepted recipe; UI work must not silently enable native/vendor execution.

Progress uses observed group phases and elapsed time. Unknown work displays activity without a fabricated percentage or ETA. Dry-run explains that it is a preview. About provides authorship, version, public website/source links and self-update actions.

Toolkit self-update checks the official source on explicit request. A preview is bound to exact commits and reports local modifications. Applying requires an idle workflow, explicit confirmation and fast-forward-only guards. It must preserve ignored local state, reject collisions/divergence, never push, reset, stash or overwrite user code, and require restarting the interface. Tracked configuration is upstream default; external private policy/UI state is user-owned. Local code edits are not settings and block automatic replacement with a clear explanation.

## Verification

Reproduce batched keyboard navigation and missing prompt focus. Exercise visible buttons, full wizard, inventory search/toggle/save, prompt Send/Cancel, resize and dry-run in isolated PTYs. Test profile/policy changes with temporary state and self-update with local Git fixtures. Verify all seven languages, Python 3.9 and full guarded suite. Review representative real renderer frames and distinguish screenshots/mock data from live execution. Publication is a separate action; this change is prepared locally for feedback.

## Native updates and concurrency refinement

The owner subsequently requested automatic execution for the installed Internet group, with DeepSeek left manual, and explicitly approved opening the native windows together. The automatic mode is a request for one fresh batch review, never an implicit permission grant. Every eligible scope appears with its source, exact target and action; all pages must be reviewed before explicit AUTO confirmation. Empty input, EOF, timeout, -y and noninteractive execution grant nothing. Declining also defers saved Internet grants for that run. Excluded targets and unresolved source conflicts remain protected.

Native-window delegation trusts the observed signed installed application to choose its offered release using existing channel settings. Legacy same-source execution is a distinct scope permitting the reviewed code-owned handler to download and transactionally replace the same installed product, with fresh identity, source and idle checks. Neither is fabricated exact-candidate recipe acceptance. Open Design has no implemented automatic payload path and is reported as unsupported; opening a window is not a substitute for such a path.

The scheduler claims one exclusive reservation for the combined Internet scope, then starts independent callbacks concurrently. Shared Google and Microsoft mechanisms are grouped. Google requires an explicit fingerprint-bound approval for all products registered with its updater, including out-of-catalog membership that is not fully enumerated. Closed helper paths must pass signing checks. Office receives only consented product IDs; the compatibility bridge does not terminate applications or rewrite Office deferral preferences. Native windows use the exact admitted paths and do not steal foreground focus. No automatic quit or restart is added.

Callbacks share one bounded observation deadline. Changed installed metadata is displayed as observed evidence, not verified latest stable or helper completion. Unconfirmed work retains the group's resource reservation. Inventory observation remains available, but system updates wait. Recovery requires a fresh review of every group member, no active owned writer, and explicit user-reported completion. A timeout cannot release a live writer's reservation.

Ordinary package-manager operations retain serialization and source ownership. The Internet group's internal concurrency must not be advertised as universal concurrency between Homebrew, App Store and every updater.
