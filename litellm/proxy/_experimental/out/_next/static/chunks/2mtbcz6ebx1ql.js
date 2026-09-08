(globalThis.TURBOPACK||(globalThis.TURBOPACK=[])).push(["object"==typeof document?document.currentScript:void 0,233565,e=>{"use strict";var t=e.i(246349);e.s(["ChevronRightIcon",()=>t.default])},755146,e=>{"use strict";var t=e.i(843476),a=e.i(451512),i=e.i(196631);e.i(233565),e.i(678784),e.s(["DropdownMenu",0,function({...e}){return(0,t.jsx)(a.Menu.Root,{"data-slot":"dropdown-menu",...e})},"DropdownMenuContent",0,function({align:e="start",alignOffset:r=0,side:n="bottom",sideOffset:o=4,className:s,...l}){return(0,t.jsx)(a.Menu.Portal,{children:(0,t.jsx)(a.Menu.Positioner,{className:"isolate z-popup outline-none",align:e,alignOffset:r,side:n,sideOffset:o,children:(0,t.jsx)(a.Menu.Popup,{"data-slot":"dropdown-menu-content",className:(0,i.cn)("z-popup max-h-(--available-height) w-(--anchor-width) min-w-32 origin-(--transform-origin) overflow-x-hidden overflow-y-auto rounded-md bg-popover p-1 text-popover-foreground shadow-md ring-1 ring-foreground/10 duration-100 outline-none data-[side=bottom]:slide-in-from-top-2 data-[side=inline-end]:slide-in-from-left-2 data-[side=inline-start]:slide-in-from-right-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:overflow-hidden data-closed:fade-out-0 data-closed:zoom-out-95",s),...l})})})},"DropdownMenuItem",0,function({className:e,inset:r,variant:n="default",...o}){return(0,t.jsx)(a.Menu.Item,{"data-slot":"dropdown-menu-item","data-inset":r,"data-variant":n,className:(0,i.cn)("group/dropdown-menu-item relative flex cursor-default items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-hidden select-none focus:bg-accent focus:text-accent-foreground not-data-[variant=destructive]:focus:**:text-accent-foreground data-inset:pl-8 data-[variant=destructive]:text-destructive data-[variant=destructive]:focus:bg-destructive/10 data-[variant=destructive]:focus:text-destructive dark:data-[variant=destructive]:focus:bg-destructive/20 data-disabled:pointer-events-none data-disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4 data-[variant=destructive]:*:[svg]:text-destructive",e),...o})},"DropdownMenuSeparator",0,function({className:e,...r}){return(0,t.jsx)(a.Menu.Separator,{"data-slot":"dropdown-menu-separator",className:(0,i.cn)("-mx-1 my-1 h-px bg-border",e),...r})},"DropdownMenuTrigger",0,function({...e}){return(0,t.jsx)(a.Menu.Trigger,{"data-slot":"dropdown-menu-trigger",...e})}])},541071,373488,e=>{"use strict";let t=(0,e.i(475254).default)("ellipsis",[["circle",{cx:"12",cy:"12",r:"1",key:"41hilf"}],["circle",{cx:"19",cy:"12",r:"1",key:"1wjl8i"}],["circle",{cx:"5",cy:"12",r:"1",key:"1pcz8c"}]]);e.s(["default",0,t],373488),e.s(["MoreHorizontal",0,t],541071)},332102,e=>{"use strict";let t=(0,e.i(475254).default)("inbox",[["polyline",{points:"22 12 16 12 14 15 10 15 8 12 2 12",key:"o97t9d"}],["path",{d:"M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z",key:"oot6mr"}]]);e.s(["Inbox",0,t],332102)},546467,e=>{"use strict";let t=(0,e.i(475254).default)("external-link",[["path",{d:"M15 3h6v6",key:"1q9fwt"}],["path",{d:"M10 14 21 3",key:"gplh6r"}],["path",{d:"M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6",key:"a6xqqp"}]]);e.s(["default",0,t])},778917,e=>{"use strict";var t=e.i(546467);e.s(["ExternalLink",()=>t.default])},180127,e=>{"use strict";let t=(0,e.i(475254).default)("arrow-left",[["path",{d:"m12 19-7-7 7-7",key:"1l729n"}],["path",{d:"M19 12H5",key:"x3x0zl"}]]);e.s(["default",0,t])},871689,e=>{"use strict";var t=e.i(180127);e.s(["ArrowLeft",()=>t.default])},845150,e=>{"use strict";var t=e.i(843476),a=e.i(271645),i=e.i(131792);let r=(e,t)=>{let a=t.trim().toLowerCase();return!a||e.label.toLowerCase().includes(a)||e.value.toLowerCase().includes(a)||(e.description?.toLowerCase().includes(a)??!1)};e.s(["MultiSelect",0,function({id:e,options:n,value:o=[],onValueChange:s,placeholder:l="Select options",emptyText:d="No options found",disabled:p=!1,loading:u=!1,allowCustomValues:c=!1,className:m}){let g=(0,i.useComboboxAnchor)(),[f,h]=(0,a.useState)(""),x=n.filter(e=>null!=e&&"string"==typeof e.value&&e.value.length>0),b=o.filter(e=>"string"==typeof e&&e.length>0).map(e=>x.find(t=>t.value===e)??{label:e,value:e}),_=f.trim(),v=x.some(e=>e.value.toLowerCase()===_.toLowerCase()),y=c&&_&&!v?[...x,{label:`Create "${_}"`,value:_}]:x;return(0,t.jsxs)(i.Combobox,{multiple:!0,items:y,value:b,onValueChange:e=>{s(Array.from(new Set(c?e.flatMap(e=>o.includes(e.value)?[e.value]:e.value.split(",").map(e=>e.trim()).filter(e=>e.length>0)):e.map(e=>e.value)))),h("")},inputValue:f,onInputValueChange:h,isItemEqualToValue:(e,t)=>e.value===t.value,itemToStringLabel:e=>e.label,filter:r,disabled:p||u,children:[(0,t.jsx)(i.ComboboxChips,{render:(0,t.jsx)("div",{ref:g}),className:`min-h-8 py-1 text-sm ${m??""}`,children:(0,t.jsx)(i.ComboboxValue,{children:a=>(0,t.jsxs)(t.Fragment,{children:[a.map(e=>(0,t.jsx)(i.ComboboxChip,{"aria-label":e.label,children:e.label},e.value)),(0,t.jsx)(i.ComboboxChipsInput,{id:e,placeholder:u?"Loading...":l,className:"min-w-24","aria-label":l||void 0}),a.length>0&&!p&&!u&&(0,t.jsx)(i.ComboboxClear,{className:"ml-auto self-center","aria-label":"Clear all"})]})})}),(0,t.jsxs)(i.ComboboxContent,{anchor:g,children:[(0,t.jsx)(i.ComboboxEmpty,{children:d}),(0,t.jsx)(i.ComboboxList,{children:e=>(0,t.jsx)(i.ComboboxItem,{value:e,disabled:e.disabled,children:(0,t.jsxs)("span",{className:"min-w-0",children:[(0,t.jsx)("span",{className:"block truncate",children:e.label}),e.description&&(0,t.jsx)("span",{className:"block truncate text-xs text-muted-foreground",children:e.description})]})},e.value)})]})]})}])},337822,e=>{"use strict";var t,a=e.i(843476);e.s([],158421),e.i(158421);var i=e.i(271645),r=e.i(956789),n=e.i(17989),o=e.i(46420);e.i(247167);var s=e.i(733332);let l=i.createContext(void 0);function d(e){let t=i.useContext(l);if(void 0===t&&!e)throw Error((0,s.default)(47));return t}var p=e.i(174080),u=e.i(301252),c=e.i(616269),m=e.i(439957),g=e.i(56434),f=e.i(264111),h=e.i(116786),x=e.i(990627),b=e.i(638396);let _={...h.popupStoreSelectors,disabled:(0,c.createSelector)(e=>e.disabled),instantType:(0,c.createSelector)(e=>e.instantType),openMethod:(0,c.createSelector)(e=>e.openMethod),openChangeReason:(0,c.createSelector)(e=>e.openChangeReason),modal:(0,c.createSelector)(e=>e.modal),focusManagerModal:(0,c.createSelector)(e=>e.focusManagerModal),stickIfOpen:(0,c.createSelector)(e=>e.stickIfOpen),titleElementId:(0,c.createSelector)(e=>e.titleElementId),descriptionElementId:(0,c.createSelector)(e=>e.descriptionElementId),openOnHover:(0,c.createSelector)(e=>e.openOnHover),closeDelay:(0,c.createSelector)(e=>e.closeDelay),hasViewport:(0,c.createSelector)(e=>e.hasViewport)};class v extends u.ReactStore{constructor(e,t,a=!1){const r={...(0,h.createInitialPopupStoreState)(),disabled:!1,modal:!1,focusManagerModal:!1,instantType:void 0,openMethod:null,openChangeReason:null,titleElementId:void 0,descriptionElementId:void 0,stickIfOpen:!0,nested:!1,openOnHover:!1,closeDelay:0,hasViewport:!1,...e},n=new x.PopupTriggerMap;r.open&&e?.mounted===void 0&&(r.mounted=!0),r.floatingRootContext=(0,h.createPopupFloatingRootContext)(n,t,a),super(r,{popupRef:i.createRef(),backdropRef:i.createRef(),internalBackdropRef:i.createRef(),onOpenChange:void 0,onOpenChangeComplete:void 0,triggerFocusTargetRef:i.createRef(),beforeContentFocusGuardRef:i.createRef(),stickIfOpenTimeout:new m.Timeout,triggerElements:n},_)}setOpen=(e,t)=>{let a=t.reason===g.REASONS.triggerHover,i=t.reason===g.REASONS.triggerPress&&0===t.event.detail,r=!e&&(t.reason===g.REASONS.escapeKey||null==t.reason),n=(0,f.attachPreventUnmountOnClose)(t),o=this.select("activeTriggerId");if(e||t.reason!==g.REASONS.closePress||null!=t.trigger||null==o||(t.trigger=this.context.triggerElements.getById(o)??this.select("activeTriggerElement")??void 0),this.context.onOpenChange?.(e,t),t.isCanceled)return;this.state.floatingRootContext.dispatchOpenChange(e,t);let s=()=>{let a={open:e,openChangeReason:t.reason};(0,f.setPopupOpenState)(a,e,t.trigger,n()),this.update(a)};a?(this.set("stickIfOpen",!0),this.context.stickIfOpenTimeout.start(b.PATIENT_CLICK_THRESHOLD,()=>{this.set("stickIfOpen",!1)}),p.flushSync(s)):s(),i||r?this.set("instantType",i?"click":"dismiss"):t.reason===g.REASONS.focusOut?this.set("instantType","focus"):this.set("instantType",void 0)};static useStore(e,t){let{store:a,internalStore:r}=(0,f.usePopupStore)(e,(e,a)=>new v(t,e,a));return i.useEffect(()=>r?.disposeEffect(),[r]),a}disposeEffect=()=>this.context.stickIfOpenTimeout.disposeEffect()}var y=e.i(675606),S=e.i(176782);function j({props:e}){let{children:t,open:r,defaultOpen:n=!1,onOpenChange:s,onOpenChangeComplete:d,modal:p=!1,handle:u,triggerId:c,defaultTriggerId:m=null}=e,h=v.useStore(u?.store,{modal:p,open:n,openProp:r,activeTriggerId:m,triggerIdProp:c});(0,f.useInitialOpenSync)(h,r,n,m),h.useControlledProp("openProp",r),h.useControlledProp("triggerIdProp",c);let x=h.useState("open"),b=h.useState("mounted"),_=h.useState("payload"),S=null!=(0,o.useFloatingParentNodeId)();h.useContextCallback("onOpenChange",s),h.useContextCallback("onOpenChangeComplete",d),(0,f.usePopupRootSync)(h,x),(0,f.useImplicitActiveTrigger)(h);let{forceUnmount:w}=(0,f.useOpenStateTransitions)(x,h,()=>{h.update({stickIfOpen:!0,openChangeReason:null})});h.useSyncedValues({modal:p,nested:S}),i.useEffect(()=>{x||h.context.stickIfOpenTimeout.clear()},[h,x]);let E=i.useCallback(()=>{h.setOpen(!1,(0,y.createChangeEventDetails)(g.REASONS.imperativeAction))},[h]);i.useImperativeHandle(e.actionsRef,()=>({unmount:w,close:E}),[w,E]);let N=x||b,k=i.useMemo(()=>({store:h}),[h]);return(0,a.jsxs)(l.Provider,{value:k,children:[N&&(0,a.jsx)(C,{store:h,modal:p}),"function"==typeof t?t({payload:_}):t]})}function C({store:e,modal:t}){let a=e.useState("floatingRootContext"),o=(0,n.useDismiss)(a,{outsidePressEvent:{mouse:"trap-focus"===t?"sloppy":"intentional",touch:"sloppy"}}),s=o.reference??r.EMPTY_OBJECT,l=o.trigger??r.EMPTY_OBJECT,d=i.useMemo(()=>(0,S.mergeProps)(f.FOCUSABLE_POPUP_PROPS,o.floating),[o.floating]);return(0,f.usePopupInteractionProps)(e,{activeTriggerProps:s,inactiveTriggerProps:l,popupProps:d}),null}var w=e.i(540886),E=e.i(405005),N=e.i(552245),k=e.i(650316),I=e.i(385689),R=e.i(872135),O=e.i(788015),T=e.i(152535),P=e.i(346570),A=e.i(32199);let M=i.forwardRef(function(e,t){let{render:r,className:n,style:o,disabled:l=!1,nativeButton:p=!0,handle:u,payload:c,openOnHover:m=!1,delay:h=300,closeDelay:x=0,id:_,...v}=e,y=d(!0),S=u?.store??y?.store;if(!S)throw Error((0,s.default)(74));let j=(0,O.useBaseUiId)(_),C=S.useState("isTriggerActive",j),M=S.useState("floatingRootContext"),$=S.useState("isOpenedByTrigger",j),D=S.useState("triggerPopupId",j),L=i.useRef(null),{registerTrigger:z,isMountedByThisTrigger:H}=(0,f.useTriggerDataForwarding)(j,L,S,{payload:c,disabled:l,openOnHover:m,closeDelay:x}),F=S.useState("openChangeReason"),B=S.useState("stickIfOpen"),G=S.useState("openMethod"),U=S.useState("focusManagerModal"),V=(0,R.useHoverReferenceInteraction)(M,{enabled:!l&&null!=M&&m&&("touch"!==G||F!==g.REASONS.triggerPress),mouseOnly:!0,move:!1,handleClose:(0,k.safePolygon)(),restMs:h,delay:{close:x},triggerElementRef:L,isActiveTrigger:C,isClosing:()=>"ending"===S.select("transitionStatus")}),q=(0,I.useClick)(M,{enabled:null!=M,stickIfOpen:B}),K=(0,A.useOpenMethodTriggerProps)(()=>S.select("open"),e=>{S.set("openMethod",e)}),Y=S.useState("triggerProps",H),{getButtonProps:W,buttonRef:Z}=(0,w.useButton)({disabled:l,native:p}),{preFocusGuardRef:J,handlePreFocusGuardFocus:Q,handleFocusTargetFocus:X}=(0,P.useTriggerFocusGuards)(S,L),ee=(0,N.useRenderElement)("button",e,{state:{disabled:l,open:$},ref:[Z,t,z,L],props:[q.reference,V,Y,K,{[b.CLICK_TRIGGER_IDENTIFIER]:"",id:j,"aria-haspopup":"dialog","aria-expanded":$,"aria-controls":D},v,W],stateAttributesMapping:{open:e=>e&&F===g.REASONS.triggerPress?E.pressableTriggerOpenStateMapping.open(e):E.triggerOpenStateMapping.open(e)}});return H&&!U?(0,a.jsxs)(i.Fragment,{children:[(0,a.jsx)(T.FocusGuard,{ref:J,onFocus:Q}),(0,a.jsx)(i.Fragment,{children:ee},j),(0,a.jsx)(T.FocusGuard,{ref:S.context.triggerFocusTargetRef,onFocus:X})]}):(0,a.jsx)(i.Fragment,{children:ee},j)});var $=e.i(726674);let D=i.createContext(void 0),L=i.forwardRef(function(e,t){let{keepMounted:i=!1,...r}=e,{store:n}=d();return n.useState("mounted")||i?(0,a.jsx)(D.Provider,{value:i,children:(0,a.jsx)($.FloatingPortal,{ref:t,...r})}):null});var z=e.i(144394),H=e.i(146376);let F=i.createContext(void 0);function B(){let e=i.useContext(F);if(!e)throw Error((0,s.default)(46));return e}var G=e.i(329365),U=e.i(426),V=e.i(222640),q=e.i(360495),K=e.i(789579),Y=e.i(33383);let W=i.forwardRef(function(e,t){let{render:r,className:n,style:l,anchor:p,positionMethod:u="absolute",side:c="bottom",align:m="center",sideOffset:f=0,alignOffset:h=0,collisionBoundary:x="clipping-ancestors",collisionPadding:_=5,arrowPadding:v=5,sticky:y=!1,disableAnchorTracking:S=!1,collisionAvoidance:j=b.POPUP_COLLISION_AVOIDANCE,...C}=e,{store:w}=d(),E=function(){let e=i.useContext(D);if(void 0===e)throw Error((0,s.default)(45));return e}(),N=(0,o.useFloatingNodeId)(),k=w.useState("floatingRootContext"),I=w.useState("mounted"),R=w.useState("open"),O=w.useState("openChangeReason"),T=w.useState("activeTriggerElement"),P=w.useState("modal"),A=w.useState("openMethod"),M=w.useState("positionerElement"),$=w.useState("instantType"),L=w.useState("transitionStatus"),B=w.useState("hasViewport"),W=i.useRef(null),Z=(0,V.useAnimationsFinished)(M,!1,!1),J=(0,G.useAnchorPositioning)({anchor:p,floatingRootContext:k,positionMethod:u,mounted:I,side:c,sideOffset:f,align:m,alignOffset:h,arrowPadding:v,collisionBoundary:x,collisionPadding:_,sticky:y,disableAnchorTracking:S,keepMounted:E,nodeId:N,collisionAvoidance:j,adaptiveOrigin:B?q.adaptiveOrigin:void 0}),Q=k.useState("domReferenceElement");(0,H.useIsoLayoutEffect)(()=>{let e=W.current;if(Q&&(W.current=Q),e&&Q&&Q!==e){w.set("instantType",void 0);let e=new AbortController;return Z(()=>{w.set("instantType","trigger-change")},e.signal),()=>{e.abort()}}},[Q,Z,w]),(0,Y.useAnchoredPopupScrollLock)(R&&!0===P&&O!==g.REASONS.triggerHover,"touch"===A,M,T);let X=i.useCallback(e=>{w.set("positionerElement",e)},[w]),ee={open:R,side:J.side,align:J.align,anchorHidden:J.anchorHidden,instant:$},et=(0,K.usePositioner)(e,ee,{styles:J.positionerStyles,transitionStatus:L,props:C,refs:[t,X],hidden:!I,inert:!R});return(0,a.jsxs)(F.Provider,{value:J,children:[I&&!0===P&&O!==g.REASONS.triggerHover&&(0,a.jsx)(U.InternalBackdrop,{ref:w.context.internalBackdropRef,inert:(0,z.inertValue)(!R),cutout:T}),(0,a.jsx)(o.FloatingNode,{id:N,children:et})]})});var Z=e.i(229315),J=e.i(61487),Q=e.i(431157),X=e.i(209407),ee=e.i(137584),et=e.i(673327),ea=e.i(96533),ei=e.i(815982),er=e.i(667865);let en=i.createContext(void 0);function eo(e){let{value:t,children:i}=e;return(0,a.jsx)(en.Provider,{value:t,children:i})}let es={...E.popupStateMapping,...X.transitionStatusMapping},el=i.forwardRef(function(e,t){let{render:r,className:n,style:o,initialFocus:s,finalFocus:l,...p}=e,{store:u}=d(),c=B(),m=null!=(0,ea.useToolbarRootContext)(!0),{context:h,hasClosePart:x}=function(){let[e,t]=i.useState(0),a=(0,er.useStableCallback)(()=>(t(e=>e+1),()=>{t(e=>Math.max(0,e-1))}));return{context:i.useMemo(()=>({register:a}),[a]),hasClosePart:e>0}}(),b=u.useState("open"),_=u.useState("openMethod"),v=u.useState("instantType"),y=u.useState("transitionStatus"),S=u.useState("popupProps"),j=u.useState("titleElementId"),C=u.useState("descriptionElementId"),w=u.useState("modal"),E=u.useState("mounted"),k=u.useState("openChangeReason"),I=u.useState("activeTriggerElement"),R=u.useState("floatingRootContext"),O=R.useState("floatingId"),T=u.useState("disabled"),P=u.useState("openOnHover"),A=u.useState("closeDelay"),M=p.id??O;(0,ee.useOpenChangeComplete)({open:b,ref:u.context.popupRef,onComplete(){b&&u.context.onOpenChangeComplete?.(!0)}}),(0,Q.useHoverFloatingInteraction)(R,{enabled:P&&!T,closeDelay:A});let $=void 0===s?(0,f.createDefaultInitialFocus)(u.context.popupRef):s,D=!1!==w&&x;u.useSyncedValue("focusManagerModal",D);let L=i.useCallback(e=>{u.set("popupElement",e)},[u]),z={open:b,side:c.side,align:c.align,instant:v,transitionStatus:y},H=(0,N.useRenderElement)("div",e,{state:z,ref:[t,u.context.popupRef,L],props:[S,{id:M,role:"dialog",...f.FOCUSABLE_POPUP_PROPS,"aria-labelledby":j,"aria-describedby":C,onKeyDown(e){m&&et.COMPOSITE_KEYS.has(e.key)&&e.stopPropagation()}},(0,ei.getDisabledMountTransitionStyles)(y),p],stateAttributesMapping:es});return(0,a.jsx)(J.FloatingFocusManager,{context:R,openInteractionType:_,modal:D,disabled:!E||k===g.REASONS.triggerHover,initialFocus:$,returnFocus:l,restoreFocus:"popup",previousFocusableElement:(0,Z.isHTMLElement)(I)?I:void 0,nextFocusableElement:u.context.triggerFocusTargetRef,beforeContentFocusGuardRef:u.context.beforeContentFocusGuardRef,children:(0,a.jsx)(eo,{value:h,children:H})})}),ed=i.forwardRef(function(e,t){let{render:a,className:i,style:r,...n}=e,{store:o}=d(),s=o.useState("open"),{arrowRef:l,side:p,align:u,arrowUncentered:c,arrowStyles:m}=B();return(0,N.useRenderElement)("div",e,{state:{open:s,side:p,align:u,uncentered:c},ref:[t,l],props:[{style:m,"aria-hidden":!0},n],stateAttributesMapping:E.popupStateMapping})}),ep={...E.popupStateMapping,...X.transitionStatusMapping},eu=i.forwardRef(function(e,t){let{render:a,className:i,style:r,...n}=e,{store:o}=d(),s=o.useState("open"),l=o.useState("mounted"),p=o.useState("transitionStatus"),u=o.useState("openChangeReason");return(0,N.useRenderElement)("div",e,{state:{open:s,transitionStatus:p},ref:[o.context.backdropRef,t],props:[{role:"presentation",hidden:!l,style:{pointerEvents:u===g.REASONS.triggerHover?"none":void 0,userSelect:"none",WebkitUserSelect:"none"}},n],stateAttributesMapping:ep})}),ec=i.forwardRef(function(e,t){let{render:a,className:i,style:r,...n}=e,{store:o}=d(),s=(0,O.useBaseUiId)(n.id);return o.useSyncedValueWithCleanup("titleElementId",s),(0,N.useRenderElement)("h2",e,{ref:t,props:[{id:s},n]})}),em=i.forwardRef(function(e,t){let{render:a,className:i,style:r,...n}=e,{store:o}=d(),s=(0,O.useBaseUiId)(n.id);return o.useSyncedValueWithCleanup("descriptionElementId",s),(0,N.useRenderElement)("p",e,{ref:t,props:[{id:s},n]})}),eg=i.forwardRef(function(e,t){let a,{render:r,className:n,style:o,disabled:s=!1,nativeButton:l=!0,...p}=e,{buttonRef:u,getButtonProps:c}=(0,w.useButton)({disabled:s,focusableWhenDisabled:!1,native:l}),{store:m}=d();return a=i.useContext(en),(0,H.useIsoLayoutEffect)(()=>a?.register(),[a]),(0,N.useRenderElement)("button",e,{ref:[t,u],props:[{onClick(e){m.setOpen(!1,(0,y.createChangeEventDetails)(g.REASONS.closePress,e.nativeEvent))}},p,c]})}),ef=((t={}).popupWidth="--popup-width",t.popupHeight="--popup-height",t);var eh=e.i(818390);let ex={activationDirection:e=>e?{"data-activation-direction":e}:null},eb=i.forwardRef(function(e,t){let{render:a,className:i,style:r,children:n,...o}=e,{store:s}=d(),{side:l}=B(),p=s.useState("instantType"),{children:u,state:c}=(0,eh.usePopupViewport)({store:s,side:l,cssVars:ef,children:n}),m={activationDirection:c.activationDirection,transitioning:c.transitioning,instant:p};return(0,N.useRenderElement)("div",e,{state:m,ref:t,props:[o,{children:u}],stateAttributesMapping:ex})});class e_{constructor(){this.store=new v}open(e){let t=e?this.store.context.triggerElements.getById(e)??void 0:void 0;if(e&&!t)throw Error((0,s.default)(80,e));this.store.setOpen(!0,(0,y.createChangeEventDetails)(g.REASONS.imperativeAction,void 0,t))}close(){this.store.setOpen(!1,(0,y.createChangeEventDetails)(g.REASONS.imperativeAction,void 0,void 0))}get isOpen(){return this.store.select("open")}}e.s(["Arrow",0,ed,"Backdrop",0,eu,"Close",0,eg,"Description",0,em,"Handle",0,e_,"Popup",0,el,"Portal",0,L,"Positioner",0,W,"Root",0,function(e){return d(!0)?(0,a.jsx)(j,{props:e}):(0,a.jsx)(o.FloatingTree,{children:(0,a.jsx)(j,{props:e})})},"Title",0,ec,"Trigger",0,M,"Viewport",0,eb,"createHandle",0,function(){return new e_}],466914);var ev=e.i(466914),ev=ev,ey=e.i(196631);e.s(["Popover",0,function({...e}){return(0,a.jsx)(ev.Root,{"data-slot":"popover",...e})},"PopoverContent",0,function({className:e,align:t="center",alignOffset:i=0,side:r="bottom",sideOffset:n=4,...o}){return(0,a.jsx)(ev.Portal,{children:(0,a.jsx)(ev.Positioner,{align:t,alignOffset:i,side:r,sideOffset:n,className:"isolate z-popup",children:(0,a.jsx)(ev.Popup,{"data-slot":"popover-content",className:(0,ey.cn)("z-popup flex w-72 origin-(--transform-origin) flex-col gap-4 rounded-md bg-popover p-4 text-sm text-popover-foreground shadow-md ring-1 ring-foreground/10 outline-hidden duration-100 data-[side=bottom]:slide-in-from-top-2 data-[side=inline-end]:slide-in-from-left-2 data-[side=inline-start]:slide-in-from-right-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",e),...o})})})},"PopoverDescription",0,function({className:e,...t}){return(0,a.jsx)(ev.Description,{"data-slot":"popover-description",className:(0,ey.cn)("text-muted-foreground",e),...t})},"PopoverTitle",0,function({className:e,...t}){return(0,a.jsx)(ev.Title,{"data-slot":"popover-title",className:(0,ey.cn)("font-medium",e),...t})},"PopoverTrigger",0,function({...e}){return(0,a.jsx)(ev.Trigger,{"data-slot":"popover-trigger",...e})}],337822)},284614,e=>{"use strict";let t=(0,e.i(475254).default)("user",[["path",{d:"M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2",key:"975kel"}],["circle",{cx:"12",cy:"7",r:"4",key:"17ys0d"}]]);e.s(["User",0,t],284614)},581418,e=>{"use strict";let t=(0,e.i(475254).default)("shield-check",[["path",{d:"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z",key:"oel41y"}],["path",{d:"m9 12 2 2 4-4",key:"dzmm74"}]]);e.s(["ShieldCheck",0,t],581418)},571353,e=>{"use strict";e.i(602869);var t=e.i(221688);let a={"api-keys":"api-keys",providers:"providers",models:"models-and-endpoints",api_ref:"api-reference","api-reference":"api-reference","llm-playground":"playground",projects:"projects",chat:"chat","access-groups":"access-groups",budgets:"budgets",workflows:"workflows","guardrails-monitor":"guardrails-monitor","mcp-servers":"mcp-servers","search-tools":"search-tools","tag-management":"tag-management","vector-stores":"vector-stores",memory:"memory",policies:"policies",guardrails:"guardrails",prompts:"prompts","tool-policies":"tool-policies",skills:"skills","claude-code-plugins":"skills",caching:"caching","cost-tracking":"cost-tracking","transform-request":"transform-request","ui-theme":"ui-theme",logs:"logs","admin-panel":"admin-panel","logging-and-alerts":"logging-and-alerts","model-hub-table":"model-hub-table",new_usage:"usage",usage:"old-usage","cost-optimization":"cost-optimization",agents:"agents","router-settings":"router-settings",users:"users",teams:"teams",organizations:"organizations"};function i(){let e=t.serverRootPath&&"/"!==t.serverRootPath?`/${t.serverRootPath.replace(/^\/+|\/+$/g,"")}`:"";return`${e}/ui`}e.s(["MIGRATED_PAGES",0,a,"legacyKeyForPathname",0,function(e){let t=i(),r=(e.startsWith(t)?e.slice(t.length):e).replace(/^\/+|\/+$/g,"");for(let[e,t]of Object.entries(a))if(r===t)return e;return null},"legacyPageHref",0,function(e){return`${i()}/?page=${e}`},"migratedHref",0,function(e){return`${i()}/${e.replace(/^\/+/,"")}`}])},922407,e=>{"use strict";var t=e.i(843476),a=e.i(519455),i=e.i(196631),r=e.i(643531),n=e.i(174886),o=e.i(271645);e.s(["default",0,({value:e,label:s,className:l,iconClassName:d="size-[15px]"})=>{let[p,u]=(0,o.useState)(!1);if((0,o.useEffect)(()=>{if(!p)return;let e=setTimeout(()=>u(!1),1200);return()=>clearTimeout(e)},[p]),!e)return null;let c=async()=>{if(navigator.clipboard)try{await navigator.clipboard.writeText(e),u(!0)}catch{u(!1)}};return(0,t.jsx)(a.Button,{type:"button",variant:"ghost",size:"icon-xs",onClick:c,"aria-label":s,title:s,className:(0,i.cn)("text-muted-foreground hover:text-primary",l),children:p?(0,t.jsx)(r.Check,{className:d}):(0,t.jsx)(n.Copy,{className:d})})}])},292639,e=>{"use strict";var t=e.i(602869),a=e.i(266027);let i=(0,e.i(243652).createQueryKeys)("uiSettings");e.s(["useUISettings",0,e=>(0,a.useQuery)({queryKey:i.list({}),queryFn:async()=>await (0,t.getUiSettings)(),staleTime:e?.staleTime??36e5,gcTime:36e5,refetchInterval:e?.refetchInterval})])},434626,e=>{"use strict";var t=e.i(271645);let a=t.forwardRef(function(e,a){return t.createElement("svg",Object.assign({xmlns:"http://www.w3.org/2000/svg",fill:"none",viewBox:"0 0 24 24",strokeWidth:2,stroke:"currentColor","aria-hidden":"true",ref:a},e),t.createElement("path",{strokeLinecap:"round",strokeLinejoin:"round",d:"M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"}))});e.s(["ExternalLinkIcon",0,a],434626)},306228,e=>{"use strict";let t=(0,e.i(475254).default)("link-2",[["path",{d:"M9 17H7A5 5 0 0 1 7 7h2",key:"8i5ue5"}],["path",{d:"M15 7h2a5 5 0 1 1 0 10h-2",key:"1b9ql8"}],["line",{x1:"8",x2:"16",y1:"12",y2:"12",key:"1jonct"}]]);e.s(["Link2",0,t],306228)},652272,209261,e=>{"use strict";var t=e.i(843476),a=e.i(271645),i=e.i(871689),r=e.i(643531),n=e.i(174886),o=e.i(306228),s=e.i(196631);let l=/^[a-zA-Z0-9][a-zA-Z0-9._-]*(\/[a-zA-Z0-9][a-zA-Z0-9._-]*)*$/,d=e=>e.trim().replace(/\/+$/,""),p=/\.(md|markdown|txt|json|ya?ml|toml)$/i,u=/^\d{1,3}(\.\d{1,3}){3}$/,c=/^[A-Za-z0-9-]+$/,m=/^[A-Za-z0-9._-]+$/,g=e=>e.pathname.split("/").filter(e=>""!==e),f=e=>{let t=e.split("/").filter(e=>""!==e);return t[t.length-1]??""},h=e=>e.toLowerCase().replace(/[^a-z0-9-]+/g,"-").replace(/-+/g,"-").replace(/^-+|-+$/g,""),x=e=>JSON.stringify({extraKnownMarketplaces:{litellm:{source:{source:"url",url:`${e}/claude-code/marketplace.json`}}}},null,2),b=e=>`/plugin install ${e.name}@litellm`;e.s(["buildMarketplaceSettingsSnippet",0,x,"formatInstallCommand",0,b,"getCategoryBadgeColor",0,e=>{if(!e)return"gray";let t=e.toLowerCase();if(t.includes("development")||t.includes("dev"))return"blue";if(t.includes("productivity")||t.includes("workflow"))return"green";if(t.includes("learning")||t.includes("education"))return"purple";if(t.includes("security")||t.includes("safety"))return"red";if(t.includes("data")||t.includes("analytics"))return"orange";else if(t.includes("integration")||t.includes("api"))return"yellow";return"gray"},"isValidEmail",0,e=>!e||/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e),"isValidSemanticVersion",0,e=>!e||/^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$/.test(e),"isValidSubPath",0,e=>{let t=d(e);return""!==t&&l.test(t)},"parseKeywords",0,e=>e&&""!==e.trim()?e.split(",").map(e=>e.trim()).filter(e=>""!==e):[],"parseSkillSource",0,(e,t)=>{let a=(e=>{let t,a=e.trim();if(""===a||a.startsWith("//"))return null;let i=/^[a-z][a-z0-9+.-]*:\/\//i.test(a)?a:`https://${a}`;try{t=new URL(i)}catch{return null}return"https:"!==t.protocol||""!==t.username||""!==t.password||!t.hostname.includes(".")||t.hostname.startsWith("[")||u.test(t.hostname)?null:t})(e);if(!a)return null;if("github.com"===a.hostname.replace(/^www\./,""))return((e,t)=>{let a=g(e);if(a.length<2)return null;let i=a[0],r=a[1].replace(/\.git$/,"");if(!c.test(i)||!m.test(r))return null;let n=`${i}/${r}`,o=`https://github.com/${n}`,s={parsed:{source:"github",repo:n},label:`GitHub repo — ${n}`,suggestedName:h(r)};if(a.length>=4&&("tree"===a[2]||"blob"===a[2])){let e=a.slice(4),t=f(e.join("/")),i=p.test(t)?e.slice(0,-1):e;if(0===i.length)return s;let r=d(i.join("/"));return l.test(r)?{parsed:{source:"git-subdir",url:o,path:r},label:`GitHub subdir — ${n} @ ${r}`,suggestedName:h(f(r))}:null}if(2!==a.length)return null;let u=d(t??"");return""!==u?l.test(u)?{parsed:{source:"git-subdir",url:o,path:u},label:`GitHub subdir — ${n} @ ${u}`,suggestedName:h(f(u))}:null:s})(a,t);if(g(a).length<2)return null;let i=`${a.protocol}//${a.host}${a.pathname.replace(/\/+$/,"")}`,r=d(t??"");return""!==r?l.test(r)?{parsed:{source:"git-subdir",url:i,path:r},label:`Git subdir — ${i} @ ${r}`,suggestedName:h(f(r))}:null:{parsed:{source:"url",url:i},label:`Git repo — ${i}`,suggestedName:h(f(a.pathname).replace(/\.git$/,""))}},"validatePluginName",0,e=>!!e&&""!==e.trim()&&/^[a-z0-9-]+$/.test(e)],209261),e.s(["default",0,({skill:e,onBack:l})=>{let d,[p,u]=(0,a.useState)("overview"),[c,m]=(0,a.useState)(null),g=(e,t)=>{navigator.clipboard.writeText(e),m(t),setTimeout(()=>m(null),2e3)},f="github"===(d=e.source).source&&d.repo?`https://github.com/${d.repo}`:"git-subdir"===d.source&&d.url?d.path?`${d.url}/tree/main/${d.path}`:d.url:"url"===d.source&&d.url?d.url:null,h=b(e),_=x(window.location.origin),v=[...e.category?[{property:"Category",value:e.category}]:[],...e.domain?[{property:"Domain",value:e.domain}]:[],...e.namespace?[{property:"Namespace",value:e.namespace}]:[],...e.version?[{property:"Version",value:e.version}]:[],...e.author?.name?[{property:"Author",value:e.author.name}]:[],...e.created_at?[{property:"Added",value:new Date(e.created_at).toLocaleDateString()}]:[]];return(0,t.jsxs)("div",{className:"py-6 pl-0 pr-8",children:[(0,t.jsxs)("div",{onClick:l,className:"mb-6 inline-flex cursor-pointer items-center gap-1.5 text-sm text-muted-foreground",children:[(0,t.jsx)(i.ArrowLeft,{className:"size-3"}),(0,t.jsx)("span",{children:"Skills"})]}),(0,t.jsxs)("div",{className:"mb-2",children:[(0,t.jsx)("h1",{className:"m-0 text-[28px] font-normal leading-tight text-foreground",children:e.name}),e.description&&(0,t.jsx)("p",{className:"mb-0 ml-0 mr-0 mt-2 text-sm leading-relaxed text-muted-foreground",children:e.description})]}),(0,t.jsx)("div",{className:"mb-7 mt-6 border-b border-border",children:(0,t.jsx)("div",{className:"flex",children:[{key:"overview",label:"Overview"},{key:"usage",label:"How to Use"}].map(e=>(0,t.jsx)("div",{onClick:()=>u(e.key),className:(0,s.cn)("-mb-px cursor-pointer border-b-[3px] px-5 py-3 text-sm",p===e.key?"border-info font-medium text-info":"border-transparent font-normal text-muted-foreground"),children:e.label},e.key))})}),"overview"===p&&(0,t.jsxs)("div",{className:"flex gap-16",children:[(0,t.jsxs)("div",{className:"min-w-0 flex-1",children:[(0,t.jsx)("h2",{className:"m-0 mb-1 text-lg font-normal text-foreground",children:"Skill Details"}),(0,t.jsx)("p",{className:"m-0 mb-4 text-[13px] text-muted-foreground",children:"Metadata registered with this skill"}),(0,t.jsxs)("table",{className:"w-full border-collapse text-sm",children:[(0,t.jsx)("thead",{children:(0,t.jsxs)("tr",{className:"border-b border-border",children:[(0,t.jsx)("th",{className:"w-40 py-3 text-left font-medium text-muted-foreground",children:"Property"}),(0,t.jsx)("th",{className:"py-3 text-left font-medium text-muted-foreground",children:e.name})]})}),(0,t.jsx)("tbody",{children:v.map((e,a)=>(0,t.jsxs)("tr",{className:"border-b border-border",children:[(0,t.jsx)("td",{className:"py-3 text-foreground",children:e.property}),(0,t.jsx)("td",{className:"py-3 text-foreground",children:e.value})]},a))})]})]}),(0,t.jsxs)("div",{className:"w-60 shrink-0",children:[(0,t.jsxs)("div",{className:"mb-6",children:[(0,t.jsx)("div",{className:"mb-1 text-xs text-muted-foreground",children:"Status"}),(0,t.jsx)("span",{className:(0,s.cn)("rounded-xl px-2.5 py-[3px] text-xs font-medium",e.enabled?"bg-success/10 text-success":"bg-muted text-muted-foreground"),children:e.enabled?"Public":"Draft"})]}),f&&(0,t.jsxs)("div",{className:"mb-6",children:[(0,t.jsx)("div",{className:"mb-1 text-xs text-muted-foreground",children:"Source"}),(0,t.jsxs)("a",{href:f,target:"_blank",rel:"noopener noreferrer",className:"flex items-center gap-1 break-all text-[13px] text-info",children:[f.replace("https://",""),(0,t.jsx)(o.Link2,{className:"size-3 shrink-0"})]})]}),e.keywords&&e.keywords.length>0&&(0,t.jsxs)("div",{className:"mb-6",children:[(0,t.jsx)("div",{className:"mb-2 text-xs text-muted-foreground",children:"Tags"}),(0,t.jsx)("div",{className:"flex flex-wrap gap-1.5",children:e.keywords.map(e=>(0,t.jsx)("span",{className:"rounded-2xl border border-border bg-card px-3 py-1 text-xs text-foreground",children:e},e))})]}),(0,t.jsxs)("div",{children:[(0,t.jsx)("div",{className:"mb-1 text-xs text-muted-foreground",children:"Skill ID"}),(0,t.jsx)("div",{className:"break-all font-mono text-xs text-foreground",children:e.id})]})]})]}),"usage"===p&&(0,t.jsxs)("div",{className:"max-w-[640px]",children:[(0,t.jsx)("h2",{className:"m-0 mb-2 text-lg font-normal text-foreground",children:"Using this skill"}),(0,t.jsx)("p",{className:"m-0 mb-6 text-sm leading-relaxed text-muted-foreground",children:"Once your proxy is set as a marketplace, enable this skill in Claude Code with one command:"}),(0,t.jsxs)("div",{className:"mb-6 overflow-hidden rounded-lg border border-border",children:[(0,t.jsxs)("div",{className:"flex items-center justify-between border-b border-border bg-muted px-4 py-2.5",children:[(0,t.jsx)("span",{className:"text-[13px] font-medium text-foreground",children:"Run in Claude Code"}),(0,t.jsxs)("button",{onClick:()=>g(h,"install"),className:(0,s.cn)("flex cursor-pointer items-center gap-1 border-none bg-transparent p-0 text-xs","install"===c?"text-success":"text-info"),children:["install"===c?(0,t.jsx)(r.Check,{className:"size-3"}):(0,t.jsx)(n.Copy,{className:"size-3"}),"install"===c?"Copied":"Copy"]})]}),(0,t.jsx)("pre",{className:"m-0 bg-card px-4 py-3.5 font-mono text-sm text-foreground",children:h})]}),(0,t.jsxs)("div",{className:"mb-4 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3",children:[(0,t.jsxs)("p",{className:"m-0 mb-2 text-[13px] leading-relaxed text-muted-foreground",children:['If you see "Plugin ',e.name,'not found in marketplace", update the catalog first:']}),(0,t.jsx)("pre",{className:"m-0 bg-transparent font-mono text-[13px] text-foreground",children:"/plugin marketplace update litellm"})]}),(0,t.jsxs)("p",{className:"m-0 text-[13px] leading-relaxed text-muted-foreground",children:["Don't have the marketplace configured yet?"," ",(0,t.jsx)("span",{onClick:()=>u("setup"),className:"cursor-pointer text-info",children:"See one-time setup →"})]})]}),"setup"===p&&(0,t.jsxs)("div",{className:"max-w-[640px]",children:[(0,t.jsx)("h2",{className:"m-0 mb-2 text-lg font-normal text-foreground",children:"One-time marketplace setup"}),(0,t.jsx)("p",{className:"m-0 mb-3 text-sm leading-relaxed text-muted-foreground",children:"Run this command in Claude Code to register the marketplace:"}),(0,t.jsxs)("div",{className:"mb-6 overflow-hidden rounded-lg border border-border",children:[(0,t.jsxs)("div",{className:"flex items-center justify-between border-b border-border bg-muted px-4 py-2.5",children:[(0,t.jsx)("span",{className:"text-[13px] font-medium text-foreground",children:"Run in Claude Code"}),(0,t.jsxs)("button",{onClick:()=>{let e=window.location.origin;g(`/plugin marketplace add ${e}/claude-code/marketplace.json`,"marketplace-cmd")},className:(0,s.cn)("flex cursor-pointer items-center gap-1 border-none bg-transparent p-0 text-xs","marketplace-cmd"===c?"text-success":"text-info"),children:["marketplace-cmd"===c?(0,t.jsx)(r.Check,{className:"size-3"}):(0,t.jsx)(n.Copy,{className:"size-3"}),"marketplace-cmd"===c?"Copied":"Copy"]})]}),(0,t.jsx)("pre",{className:"m-0 bg-card px-4 py-3.5 font-mono text-[13px] text-foreground",children:`/plugin marketplace add ${window.location.origin}/claude-code/marketplace.json`})]}),(0,t.jsxs)("p",{className:"m-0 mb-3 text-sm leading-relaxed text-muted-foreground",children:["Or add this to ",(0,t.jsx)("code",{className:"rounded bg-muted px-1.5 py-px text-[13px]",children:"~/.claude/settings.json"})," ","for a persistent configuration:"]}),(0,t.jsxs)("div",{className:"overflow-hidden rounded-lg border border-border",children:[(0,t.jsxs)("div",{className:"flex items-center justify-between border-b border-border bg-muted px-4 py-2.5",children:[(0,t.jsx)("span",{className:"text-[13px] font-medium text-foreground",children:"~/.claude/settings.json"}),(0,t.jsxs)("button",{onClick:()=>g(_,"settings"),className:(0,s.cn)("flex cursor-pointer items-center gap-1 border-none bg-transparent p-0 text-xs","settings"===c?"text-success":"text-info"),children:["settings"===c?(0,t.jsx)(r.Check,{className:"size-3"}):(0,t.jsx)(n.Copy,{className:"size-3"}),"settings"===c?"Copied":"Copy"]})]}),(0,t.jsx)("pre",{className:"m-0 bg-card px-4 py-3.5 font-mono text-[13px] text-foreground",children:_})]})]})]})}],652272)},899426,e=>{"use strict";let t=e=>e.trim().toLowerCase();function a(e,a){let i=t(e);if(""===i)return!0;let r=a.filter(e=>"string"==typeof e).map(e=>e.toLowerCase());return!!r.some(e=>e.includes(i))||i.split(/\s+/).every(e=>r.some(t=>t.includes(e)))}e.s(["filterBySearchTerm",0,function(e,t,i){return e.filter(e=>a(t,i(e)))},"matchesSearchTerm",0,a,"rankBySearchRelevance",0,function(e,a,i){let r=t(a);if(""===r)return[...e];let n=e=>{let t=i(e).toLowerCase();return 1e3*(t===r)+100*!!t.startsWith(r)+(1e3-t.length)};return[...e].sort((e,t)=>n(t)-n(e))}])},909947,865361,e=>{"use strict";var t,a,i=((t={}).AUDIO_SPEECH="audio_speech",t.AUDIO_TRANSCRIPTION="audio_transcription",t.IMAGE_GENERATION="image_generation",t.VIDEO_GENERATION="video_generation",t.CHAT="chat",t.COMPLETION="completion",t.RESPONSES="responses",t.IMAGE_EDITS="image_edit",t.ANTHROPIC_MESSAGES="anthropic_messages",t.EMBEDDING="embedding",t.REALTIME="realtime",t),r=((a={}).IMAGE="image",a.VIDEO="video",a.CHAT="chat",a.RESPONSES="responses",a.IMAGE_EDITS="image_edits",a.ANTHROPIC_MESSAGES="anthropic_messages",a.EMBEDDINGS="embeddings",a.SPEECH="speech",a.TRANSCRIPTION="transcription",a.A2A_AGENTS="a2a_agents",a.MCP="mcp",a.REALTIME="realtime",a.INTERACTIONS="interactions",a);let n={image_generation:"image",video_generation:"video",chat:"chat",completion:"chat",responses:"responses",image_edit:"image_edits",anthropic_messages:"anthropic_messages",audio_speech:"speech",audio_transcription:"transcription",embedding:"embeddings",realtime:"realtime"};e.s(["EndpointType",()=>r,"ModelMode",()=>i,"getEndpointType",0,e=>Object.values(i).includes(e)?n[e]:"chat"],865361),e.s(["generateCodeSnippet",0,e=>{let t,{apiKeySource:a,accessToken:i,apiKey:n,inputMessage:o,chatHistory:s,selectedTags:l,selectedVectorStores:d,selectedGuardrails:p,selectedPolicies:u,selectedVoice:c,endpointType:m,selectedModel:g,selectedSdk:f,proxySettings:h}=e,x="session"===a?i:n,b=window.location.origin,_=h?.LITELLM_UI_API_DOC_BASE_URL;_&&_.trim()?b=_:h?.PROXY_BASE_URL&&(b=h.PROXY_BASE_URL);let v=o||"Your prompt here",y=v.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\n/g,"\\n"),S=s.filter(e=>!e.isImage).map(({role:e,content:t})=>({role:e,content:t})),j={};l.length>0&&(j.tags=l),d.length>0&&(j.vector_stores=d),p.length>0&&(j.guardrails=p),u.length>0&&(j.policies=u);let C=g||"your-model-name",w="azure"===f?`import openai

client = openai.AzureOpenAI(
	api_key="${x||"YOUR_LITELLM_API_KEY"}",
	azure_endpoint="${b}",
	api_version="2024-02-01"
)`:`import openai

client = openai.OpenAI(
	api_key="${x||"YOUR_LITELLM_API_KEY"}",
	base_url="${b}"
)`;switch(m){case r.CHAT:{let e=Object.keys(j).length>0,a="";if(e){let e=JSON.stringify({metadata:j},null,2).split("\n").map(e=>" ".repeat(4)+e).join("\n").trim();a=`,
    extra_body=${e}`}let i=S.length>0?S:[{role:"user",content:v}];t=`
import base64

# Helper function to encode images to base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Example with text only
response = client.chat.completions.create(
    model="${C}",
    messages=${JSON.stringify(i,null,4)}${a}
)

print(response)

# Example with image or PDF (uncomment and provide file path to use)
# base64_file = encode_image("path/to/your/file.jpg")  # or .pdf
# response_with_file = client.chat.completions.create(
#     model="${C}",
#     messages=[
#         {
#             "role": "user",
#             "content": [
#                 {
#                     "type": "text",
#                     "text": "${y}"
#                 },
#                 {
#                     "type": "image_url",
#                     "image_url": {
#                         "url": f"data:image/jpeg;base64,{base64_file}"  # or data:application/pdf;base64,{base64_file}
#                     }
#                 }
#             ]
#         }
#     ]${a}
# )
# print(response_with_file)
`;break}case r.RESPONSES:{let e=Object.keys(j).length>0,a="";if(e){let e=JSON.stringify({metadata:j},null,2).split("\n").map(e=>" ".repeat(4)+e).join("\n").trim();a=`,
    extra_body=${e}`}let i=S.length>0?S:[{role:"user",content:v}];t=`
import base64

# Helper function to encode images to base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Example with text only
response = client.responses.create(
    model="${C}",
    input=${JSON.stringify(i,null,4)}${a}
)

print(response.output_text)

# Example with image or PDF (uncomment and provide file path to use)
# base64_file = encode_image("path/to/your/file.jpg")  # or .pdf
# response_with_file = client.responses.create(
#     model="${C}",
#     input=[
#         {
#             "role": "user",
#             "content": [
#                 {"type": "input_text", "text": "${y}"},
#                 {
#                     "type": "input_image",
#                     "image_url": f"data:image/jpeg;base64,{base64_file}",  # or data:application/pdf;base64,{base64_file}
#                 },
#             ],
#         }
#     ]${a}
# )
# print(response_with_file.output_text)
`;break}case r.IMAGE:t="azure"===f?`
# NOTE: The Azure SDK does not have a direct equivalent to the multi-modal 'responses.create' method shown for OpenAI.
# This snippet uses 'client.images.generate' and will create a new image based on your prompt.
# It does not use the uploaded image, as 'client.images.generate' does not support image inputs in this context.
import os
import requests
import json
import time
from PIL import Image

result = client.images.generate(
	model="${C}",
	prompt="${o}",
	n=1
)

json_response = json.loads(result.model_dump_json())

# Set the directory for the stored image
image_dir = os.path.join(os.curdir, 'images')

# If the directory doesn't exist, create it
if not os.path.isdir(image_dir):
	os.mkdir(image_dir)

# Initialize the image path
image_filename = f"generated_image_{int(time.time())}.png"
image_path = os.path.join(image_dir, image_filename)

try:
	# Retrieve the generated image
	if json_response.get("data") && len(json_response["data"]) > 0 && json_response["data"][0].get("url"):
			image_url = json_response["data"][0]["url"]
			generated_image = requests.get(image_url).content
			with open(image_path, "wb") as image_file:
					image_file.write(generated_image)

			print(f"Image saved to {image_path}")
			# Display the image
			image = Image.open(image_path)
			image.show()
	else:
			print("Could not find image URL in response.")
			print("Full response:", json_response)
except Exception as e:
	print(f"An error occurred: {e}")
	print("Full response:", json_response)
`:`
import base64
import os
import time
import json
from PIL import Image
import requests

# Helper function to encode images to base64
def encode_image(image_path):
	with open(image_path, "rb") as image_file:
			return base64.b64encode(image_file.read()).decode('utf-8')

# Helper function to create a file (simplified for this example)
def create_file(image_path):
	# In a real implementation, this would upload the file to OpenAI
	# For this example, we'll just return a placeholder ID
	return f"file_{os.path.basename(image_path).replace('.', '_')}"

# The prompt entered by the user
prompt = "${y}"

# Encode images to base64
base64_image1 = encode_image("body-lotion.png")
base64_image2 = encode_image("soap.png")

# Create file IDs
file_id1 = create_file("body-lotion.png")
file_id2 = create_file("incense-kit.png")

response = client.responses.create(
	model="${C}",
	input=[
			{
					"role": "user",
					"content": [
							{"type": "input_text", "text": prompt},
							{
									"type": "input_image",
									"image_url": f"data:image/jpeg;base64,{base64_image1}",
							},
							{
									"type": "input_image",
									"image_url": f"data:image/jpeg;base64,{base64_image2}",
							},
							{
									"type": "input_image",
									"file_id": file_id1,
							},
							{
									"type": "input_image",
									"file_id": file_id2,
							}
					],
			}
	],
	tools=[{"type": "image_generation"}],
)

# Process the response
image_generation_calls = [
	output
	for output in response.output
	if output.type == "image_generation_call"
]

image_data = [output.result for output in image_generation_calls]

if image_data:
	image_base64 = image_data[0]
	image_filename = f"edited_image_{int(time.time())}.png"
	with open(image_filename, "wb") as f:
			f.write(base64.b64decode(image_base64))
	print(f"Image saved to {image_filename}")
else:
	# If no image is generated, there might be a text response with an explanation
	text_response = [output.text for output in response.output if hasattr(output, 'text')]
	if text_response:
			print("No image generated. Model response:")
			print("\\n".join(text_response))
	else:
			print("No image data found in response.")
	print("Full response for debugging:")
	print(response)
`;break;case r.IMAGE_EDITS:t="azure"===f?`
import base64
import os
import time
import json
from PIL import Image
import requests

# Helper function to encode images to base64
def encode_image(image_path):
	with open(image_path, "rb") as image_file:
			return base64.b64encode(image_file.read()).decode('utf-8')

# The prompt entered by the user
prompt = "${y}"

# Encode images to base64
base64_image1 = encode_image("body-lotion.png")
base64_image2 = encode_image("soap.png")

# Create file IDs
file_id1 = create_file("body-lotion.png")
file_id2 = create_file("incense-kit.png")

response = client.responses.create(
	model="${C}",
	input=[
			{
					"role": "user",
					"content": [
							{"type": "input_text", "text": prompt},
							{
									"type": "input_image",
									"image_url": f"data:image/jpeg;base64,{base64_image1}",
							},
							{
									"type": "input_image",
									"image_url": f"data:image/jpeg;base64,{base64_image2}",
							},
							{
									"type": "input_image",
									"file_id": file_id1,
							},
							{
									"type": "input_image",
									"file_id": file_id2,
							}
					],
			}
	],
	tools=[{"type": "image_generation"}],
)

# Process the response
image_generation_calls = [
	output
	for output in response.output
	if output.type == "image_generation_call"
]

image_data = [output.result for output in image_generation_calls]

if image_data:
	image_base64 = image_data[0]
	image_filename = f"edited_image_{int(time.time())}.png"
	with open(image_filename, "wb") as f:
			f.write(base64.b64decode(image_base64))
	print(f"Image saved to {image_filename}")
else:
	# If no image is generated, there might be a text response with an explanation
	text_response = [output.text for output in response.output if hasattr(output, 'text')]
	if text_response:
			print("No image generated. Model response:")
			print("\\n".join(text_response))
	else:
			print("No image data found in response.")
	print("Full response for debugging:")
	print(response)
`:`
import base64
import os
import time

# Helper function to encode images to base64
def encode_image(image_path):
	with open(image_path, "rb") as image_file:
			return base64.b64encode(image_file.read()).decode('utf-8')

# Helper function to create a file (simplified for this example)
def create_file(image_path):
	# In a real implementation, this would upload the file to OpenAI
	# For this example, we'll just return a placeholder ID
	return f"file_{os.path.basename(image_path).replace('.', '_')}"

# The prompt entered by the user
prompt = "${y}"

# Encode images to base64
base64_image1 = encode_image("body-lotion.png")
base64_image2 = encode_image("soap.png")

# Create file IDs
file_id1 = create_file("body-lotion.png")
file_id2 = create_file("incense-kit.png")

response = client.responses.create(
	model="${C}",
	input=[
			{
					"role": "user",
					"content": [
							{"type": "input_text", "text": prompt},
							{
									"type": "input_image",
									"image_url": f"data:image/jpeg;base64,{base64_image1}",
							},
							{
									"type": "input_image",
									"image_url": f"data:image/jpeg;base64,{base64_image2}",
							},
							{
									"type": "input_image",
									"file_id": file_id1,
							},
							{
									"type": "input_image",
									"file_id": file_id2,
							}
					],
			}
	],
	tools=[{"type": "image_generation"}],
)

# Process the response
image_generation_calls = [
	output
	for output in response.output
	if output.type == "image_generation_call"
]

image_data = [output.result for output in image_generation_calls]

if image_data:
	image_base64 = image_data[0]
	image_filename = f"edited_image_{int(time.time())}.png"
	with open(image_filename, "wb") as f:
			f.write(base64.b64decode(image_base64))
	print(f"Image saved to {image_filename}")
else:
	# If no image is generated, there might be a text response with an explanation
	text_response = [output.text for output in response.output if hasattr(output, 'text')]
	if text_response:
			print("No image generated. Model response:")
			print("\\n".join(text_response))
	else:
			print("No image data found in response.")
	print("Full response for debugging:")
	print(response)
`;break;case r.EMBEDDINGS:t=`
response = client.embeddings.create(
	input="${o||"Your string here"}",
	model="${C}",
	encoding_format="base64" # or "float"
)

print(response.data[0].embedding)
`;break;case r.TRANSCRIPTION:t=`
# Open the audio file
audio_file = open("path/to/your/audio/file.mp3", "rb")

# Make the transcription request
response = client.audio.transcriptions.create(
	model="${C}",
	file=audio_file${o?`,
	prompt="${o.replace(/\\/g,"\\\\").replace(/"/g,'\\"')}"`:""}
)

print(response.text)
`;break;case r.SPEECH:t=`
# Make the text-to-speech request
response = client.audio.speech.create(
	model="${C}",
	input="${o||"Your text to convert to speech here"}",
	voice="${c}"  # Options: alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer
)

# Save the audio to a file
output_filename = "output_speech.mp3"
response.stream_to_file(output_filename)
print(f"Audio saved to {output_filename}")

# Optional: Customize response format and speed
# response = client.audio.speech.create(
#     model="${C}",
#     input="${o||"Your text to convert to speech here"}",
#     voice="alloy",
#     response_format="mp3",  # Options: mp3, opus, aac, flac, wav, pcm
#     speed=1.0  # Range: 0.25 to 4.0
# )
# response.stream_to_file("output_speech.mp3")
`;break;default:t="\n# Code generation for this endpoint is not implemented yet."}return`${w}
${t}`}],909947)},560280,e=>{"use strict";var t=e.i(843476),a=e.i(271645),i=e.i(618566),r=e.i(976883);function n(){let e=(0,i.useSearchParams)().get("key"),[n,o]=(0,a.useState)(null);return(0,a.useEffect)(()=>{e&&o(e)},[e]),(0,t.jsx)(r.default,{accessToken:n})}e.s(["default",0,function(){return(0,t.jsx)(a.Suspense,{fallback:(0,t.jsx)("div",{className:"flex items-center justify-center min-h-screen",children:"Loading..."}),children:(0,t.jsx)(n,{})})}])}]);