(globalThis.TURBOPACK||(globalThis.TURBOPACK=[])).push(["object"==typeof document?document.currentScript:void 0,541071,373488,e=>{"use strict";let t=(0,e.i(475254).default)("ellipsis",[["circle",{cx:"12",cy:"12",r:"1",key:"41hilf"}],["circle",{cx:"19",cy:"12",r:"1",key:"1wjl8i"}],["circle",{cx:"5",cy:"12",r:"1",key:"1pcz8c"}]]);e.s(["default",0,t],373488),e.s(["MoreHorizontal",0,t],541071)},332102,e=>{"use strict";let t=(0,e.i(475254).default)("inbox",[["polyline",{points:"22 12 16 12 14 15 10 15 8 12 2 12",key:"o97t9d"}],["path",{d:"M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z",key:"oot6mr"}]]);e.s(["Inbox",0,t],332102)},68155,e=>{"use strict";var t=e.i(271645);let r=t.forwardRef(function(e,r){return t.createElement("svg",Object.assign({xmlns:"http://www.w3.org/2000/svg",fill:"none",viewBox:"0 0 24 24",strokeWidth:2,stroke:"currentColor","aria-hidden":"true",ref:r},e),t.createElement("path",{strokeLinecap:"round",strokeLinejoin:"round",d:"M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"}))});e.s(["TrashIcon",0,r],68155)},250980,e=>{"use strict";var t=e.i(271645);let r=t.forwardRef(function(e,r){return t.createElement("svg",Object.assign({xmlns:"http://www.w3.org/2000/svg",fill:"none",viewBox:"0 0 24 24",strokeWidth:2,stroke:"currentColor","aria-hidden":"true",ref:r},e),t.createElement("path",{strokeLinecap:"round",strokeLinejoin:"round",d:"M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z"}))});e.s(["PlusCircleIcon",0,r],250980)},180127,e=>{"use strict";let t=(0,e.i(475254).default)("arrow-left",[["path",{d:"m12 19-7-7 7-7",key:"1l729n"}],["path",{d:"M19 12H5",key:"x3x0zl"}]]);e.s(["default",0,t])},871689,e=>{"use strict";var t=e.i(180127);e.s(["ArrowLeft",()=>t.default])},845150,e=>{"use strict";var t=e.i(843476),r=e.i(271645),a=e.i(131792);let i=(e,t)=>{let r=t.trim().toLowerCase();return!r||e.label.toLowerCase().includes(r)||e.value.toLowerCase().includes(r)||(e.description?.toLowerCase().includes(r)??!1)};e.s(["MultiSelect",0,function({id:e,options:s,value:n=[],onValueChange:o,placeholder:l="Select options",emptyText:d="No options found",disabled:p=!1,loading:m=!1,allowCustomValues:c=!1,className:u}){let g=(0,a.useComboboxAnchor)(),[f,h]=(0,r.useState)(""),x=s.filter(e=>null!=e&&"string"==typeof e.value&&e.value.length>0),b=n.filter(e=>"string"==typeof e&&e.length>0).map(e=>x.find(t=>t.value===e)??{label:e,value:e}),_=f.trim(),v=x.some(e=>e.value.toLowerCase()===_.toLowerCase()),j=c&&_&&!v?[...x,{label:`Create "${_}"`,value:_}]:x;return(0,t.jsxs)(a.Combobox,{multiple:!0,items:j,value:b,onValueChange:e=>{o(Array.from(new Set(c?e.flatMap(e=>n.includes(e.value)?[e.value]:e.value.split(",").map(e=>e.trim()).filter(e=>e.length>0)):e.map(e=>e.value)))),h("")},inputValue:f,onInputValueChange:h,isItemEqualToValue:(e,t)=>e.value===t.value,itemToStringLabel:e=>e.label,filter:i,disabled:p||m,children:[(0,t.jsx)(a.ComboboxChips,{render:(0,t.jsx)("div",{ref:g}),className:`min-h-8 py-1 text-sm ${u??""}`,children:(0,t.jsx)(a.ComboboxValue,{children:r=>(0,t.jsxs)(t.Fragment,{children:[r.map(e=>(0,t.jsx)(a.ComboboxChip,{"aria-label":e.label,children:e.label},e.value)),(0,t.jsx)(a.ComboboxChipsInput,{id:e,placeholder:m?"Loading...":l,className:"min-w-24","aria-label":l||void 0}),r.length>0&&!p&&!m&&(0,t.jsx)(a.ComboboxClear,{className:"ml-auto self-center","aria-label":"Clear all"})]})})}),(0,t.jsxs)(a.ComboboxContent,{anchor:g,children:[(0,t.jsx)(a.ComboboxEmpty,{children:d}),(0,t.jsx)(a.ComboboxList,{children:e=>(0,t.jsx)(a.ComboboxItem,{value:e,disabled:e.disabled,children:(0,t.jsxs)("span",{className:"min-w-0",children:[(0,t.jsx)("span",{className:"block truncate",children:e.label}),e.description&&(0,t.jsx)("span",{className:"block truncate text-xs text-muted-foreground",children:e.description})]})},e.value)})]})]})}])},871943,502547,e=>{"use strict";var t=e.i(271645);let r=t.forwardRef(function(e,r){return t.createElement("svg",Object.assign({xmlns:"http://www.w3.org/2000/svg",fill:"none",viewBox:"0 0 24 24",strokeWidth:2,stroke:"currentColor","aria-hidden":"true",ref:r},e),t.createElement("path",{strokeLinecap:"round",strokeLinejoin:"round",d:"M19 9l-7 7-7-7"}))});e.s(["ChevronDownIcon",0,r],871943);let a=t.forwardRef(function(e,r){return t.createElement("svg",Object.assign({xmlns:"http://www.w3.org/2000/svg",fill:"none",viewBox:"0 0 24 24",strokeWidth:2,stroke:"currentColor","aria-hidden":"true",ref:r},e),t.createElement("path",{strokeLinecap:"round",strokeLinejoin:"round",d:"M9 5l7 7-7 7"}))});e.s(["ChevronRightIcon",0,a],502547)},278587,e=>{"use strict";var t=e.i(271645);let r=t.forwardRef(function(e,r){return t.createElement("svg",Object.assign({xmlns:"http://www.w3.org/2000/svg",fill:"none",viewBox:"0 0 24 24",strokeWidth:2,stroke:"currentColor","aria-hidden":"true",ref:r},e),t.createElement("path",{strokeLinecap:"round",strokeLinejoin:"round",d:"M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"}))});e.s(["RefreshIcon",0,r],278587)},360820,e=>{"use strict";var t=e.i(271645);let r=t.forwardRef(function(e,r){return t.createElement("svg",Object.assign({xmlns:"http://www.w3.org/2000/svg",fill:"none",viewBox:"0 0 24 24",strokeWidth:2,stroke:"currentColor","aria-hidden":"true",ref:r},e),t.createElement("path",{strokeLinecap:"round",strokeLinejoin:"round",d:"M5 15l7-7 7 7"}))});e.s(["ChevronUpIcon",0,r],360820)},434626,e=>{"use strict";var t=e.i(271645);let r=t.forwardRef(function(e,r){return t.createElement("svg",Object.assign({xmlns:"http://www.w3.org/2000/svg",fill:"none",viewBox:"0 0 24 24",strokeWidth:2,stroke:"currentColor","aria-hidden":"true",ref:r},e),t.createElement("path",{strokeLinecap:"round",strokeLinejoin:"round",d:"M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"}))});e.s(["ExternalLinkIcon",0,r],434626)},902555,e=>{"use strict";var t=e.i(843476),r=e.i(746798),a=e.i(271645);let i=a.forwardRef(function(e,t){return a.createElement("svg",Object.assign({xmlns:"http://www.w3.org/2000/svg",fill:"none",viewBox:"0 0 24 24",strokeWidth:2,stroke:"currentColor","aria-hidden":"true",ref:t},e),a.createElement("path",{strokeLinecap:"round",strokeLinejoin:"round",d:"M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"}))}),s=a.forwardRef(function(e,t){return a.createElement("svg",Object.assign({xmlns:"http://www.w3.org/2000/svg",fill:"none",viewBox:"0 0 24 24",strokeWidth:2,stroke:"currentColor","aria-hidden":"true",ref:t},e),a.createElement("path",{strokeLinecap:"round",strokeLinejoin:"round",d:"M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"}),a.createElement("path",{strokeLinecap:"round",strokeLinejoin:"round",d:"M21 12a9 9 0 11-18 0 9 9 0 0118 0z"}))});var n=e.i(278587),o=e.i(68155),l=e.i(360820),d=e.i(871943),p=e.i(434626);let m=a.forwardRef(function(e,t){return a.createElement("svg",Object.assign({xmlns:"http://www.w3.org/2000/svg",fill:"none",viewBox:"0 0 24 24",strokeWidth:2,stroke:"currentColor","aria-hidden":"true",ref:t},e),a.createElement("path",{strokeLinecap:"round",strokeLinejoin:"round",d:"M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"}))});var c=e.i(196631);function u({icon:e,onClick:r,className:a,disabled:i,dataTestId:s}){return i?(0,t.jsx)("span",{className:"inline-flex shrink-0 cursor-not-allowed items-center justify-center p-1.5 opacity-50","data-testid":s,children:(0,t.jsx)(e,{className:"size-5 shrink-0"})}):(0,t.jsx)("span",{className:(0,c.cx)("inline-flex shrink-0 cursor-pointer items-center justify-center p-1.5",a),onClick:r,"data-testid":s,children:(0,t.jsx)(e,{className:"size-5 shrink-0"})})}let g={Edit:{icon:i,className:"hover:text-info"},Delete:{icon:o.TrashIcon,className:"hover:text-destructive"},Test:{icon:s,className:"hover:text-info"},Regenerate:{icon:n.RefreshIcon,className:"hover:text-success"},Up:{icon:l.ChevronUpIcon,className:"hover:text-info"},Down:{icon:d.ChevronDownIcon,className:"hover:text-info"},Open:{icon:p.ExternalLinkIcon,className:"hover:text-success"},Copy:{icon:m,className:"hover:text-info"}};e.s(["default",0,function({onClick:e,tooltipText:a,disabled:i=!1,disabledTooltipText:s,dataTestId:n,variant:o}){let{icon:l,className:d}=g[o],p=i?s:a,m=(0,t.jsx)(u,{icon:l,onClick:e,className:d,disabled:i,dataTestId:n});return p?(0,t.jsx)(r.TooltipProvider,{children:(0,t.jsxs)(r.Tooltip,{children:[(0,t.jsx)(r.TooltipTrigger,{render:(0,t.jsx)("span",{}),children:m}),(0,t.jsx)(r.TooltipContent,{children:p})]})}):(0,t.jsx)("span",{children:m})}],902555)},455037,e=>{"use strict";var t=e.i(494144);e.s(["prism",()=>t.default])},306228,e=>{"use strict";let t=(0,e.i(475254).default)("link-2",[["path",{d:"M9 17H7A5 5 0 0 1 7 7h2",key:"8i5ue5"}],["path",{d:"M15 7h2a5 5 0 1 1 0 10h-2",key:"1b9ql8"}],["line",{x1:"8",x2:"16",y1:"12",y2:"12",key:"1jonct"}]]);e.s(["Link2",0,t],306228)},909947,865361,e=>{"use strict";var t,r,a=((t={}).AUDIO_SPEECH="audio_speech",t.AUDIO_TRANSCRIPTION="audio_transcription",t.IMAGE_GENERATION="image_generation",t.VIDEO_GENERATION="video_generation",t.CHAT="chat",t.COMPLETION="completion",t.RESPONSES="responses",t.IMAGE_EDITS="image_edit",t.ANTHROPIC_MESSAGES="anthropic_messages",t.EMBEDDING="embedding",t.REALTIME="realtime",t),i=((r={}).IMAGE="image",r.VIDEO="video",r.CHAT="chat",r.RESPONSES="responses",r.IMAGE_EDITS="image_edits",r.ANTHROPIC_MESSAGES="anthropic_messages",r.EMBEDDINGS="embeddings",r.SPEECH="speech",r.TRANSCRIPTION="transcription",r.A2A_AGENTS="a2a_agents",r.MCP="mcp",r.REALTIME="realtime",r.INTERACTIONS="interactions",r);let s={image_generation:"image",video_generation:"video",chat:"chat",completion:"chat",responses:"responses",image_edit:"image_edits",anthropic_messages:"anthropic_messages",audio_speech:"speech",audio_transcription:"transcription",embedding:"embeddings",realtime:"realtime"};e.s(["EndpointType",()=>i,"ModelMode",()=>a,"getEndpointType",0,e=>Object.values(a).includes(e)?s[e]:"chat"],865361),e.s(["generateCodeSnippet",0,e=>{let t,{apiKeySource:r,accessToken:a,apiKey:s,inputMessage:n,chatHistory:o,selectedTags:l,selectedVectorStores:d,selectedGuardrails:p,selectedPolicies:m,selectedVoice:c,endpointType:u,selectedModel:g,selectedSdk:f,proxySettings:h}=e,x="session"===r?a:s,b=window.location.origin,_=h?.LITELLM_UI_API_DOC_BASE_URL;_&&_.trim()?b=_:h?.PROXY_BASE_URL&&(b=h.PROXY_BASE_URL);let v=n||"Your prompt here",j=v.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\n/g,"\\n"),w=o.filter(e=>!e.isImage).map(({role:e,content:t})=>({role:e,content:t})),y={};l.length>0&&(y.tags=l),d.length>0&&(y.vector_stores=d),p.length>0&&(y.guardrails=p),m.length>0&&(y.policies=m);let k=g||"your-model-name",N="azure"===f?`import openai

client = openai.AzureOpenAI(
	api_key="${x||"YOUR_LITELLM_API_KEY"}",
	azure_endpoint="${b}",
	api_version="2024-02-01"
)`:`import openai

client = openai.OpenAI(
	api_key="${x||"YOUR_LITELLM_API_KEY"}",
	base_url="${b}"
)`;switch(u){case i.CHAT:{let e=Object.keys(y).length>0,r="";if(e){let e=JSON.stringify({metadata:y},null,2).split("\n").map(e=>" ".repeat(4)+e).join("\n").trim();r=`,
    extra_body=${e}`}let a=w.length>0?w:[{role:"user",content:v}];t=`
import base64

# Helper function to encode images to base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Example with text only
response = client.chat.completions.create(
    model="${k}",
    messages=${JSON.stringify(a,null,4)}${r}
)

print(response)

# Example with image or PDF (uncomment and provide file path to use)
# base64_file = encode_image("path/to/your/file.jpg")  # or .pdf
# response_with_file = client.chat.completions.create(
#     model="${k}",
#     messages=[
#         {
#             "role": "user",
#             "content": [
#                 {
#                     "type": "text",
#                     "text": "${j}"
#                 },
#                 {
#                     "type": "image_url",
#                     "image_url": {
#                         "url": f"data:image/jpeg;base64,{base64_file}"  # or data:application/pdf;base64,{base64_file}
#                     }
#                 }
#             ]
#         }
#     ]${r}
# )
# print(response_with_file)
`;break}case i.RESPONSES:{let e=Object.keys(y).length>0,r="";if(e){let e=JSON.stringify({metadata:y},null,2).split("\n").map(e=>" ".repeat(4)+e).join("\n").trim();r=`,
    extra_body=${e}`}let a=w.length>0?w:[{role:"user",content:v}];t=`
import base64

# Helper function to encode images to base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Example with text only
response = client.responses.create(
    model="${k}",
    input=${JSON.stringify(a,null,4)}${r}
)

print(response.output_text)

# Example with image or PDF (uncomment and provide file path to use)
# base64_file = encode_image("path/to/your/file.jpg")  # or .pdf
# response_with_file = client.responses.create(
#     model="${k}",
#     input=[
#         {
#             "role": "user",
#             "content": [
#                 {"type": "input_text", "text": "${j}"},
#                 {
#                     "type": "input_image",
#                     "image_url": f"data:image/jpeg;base64,{base64_file}",  # or data:application/pdf;base64,{base64_file}
#                 },
#             ],
#         }
#     ]${r}
# )
# print(response_with_file.output_text)
`;break}case i.IMAGE:t="azure"===f?`
# NOTE: The Azure SDK does not have a direct equivalent to the multi-modal 'responses.create' method shown for OpenAI.
# This snippet uses 'client.images.generate' and will create a new image based on your prompt.
# It does not use the uploaded image, as 'client.images.generate' does not support image inputs in this context.
import os
import requests
import json
import time
from PIL import Image

result = client.images.generate(
	model="${k}",
	prompt="${n}",
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
prompt = "${j}"

# Encode images to base64
base64_image1 = encode_image("body-lotion.png")
base64_image2 = encode_image("soap.png")

# Create file IDs
file_id1 = create_file("body-lotion.png")
file_id2 = create_file("incense-kit.png")

response = client.responses.create(
	model="${k}",
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
`;break;case i.IMAGE_EDITS:t="azure"===f?`
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
prompt = "${j}"

# Encode images to base64
base64_image1 = encode_image("body-lotion.png")
base64_image2 = encode_image("soap.png")

# Create file IDs
file_id1 = create_file("body-lotion.png")
file_id2 = create_file("incense-kit.png")

response = client.responses.create(
	model="${k}",
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
prompt = "${j}"

# Encode images to base64
base64_image1 = encode_image("body-lotion.png")
base64_image2 = encode_image("soap.png")

# Create file IDs
file_id1 = create_file("body-lotion.png")
file_id2 = create_file("incense-kit.png")

response = client.responses.create(
	model="${k}",
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
`;break;case i.EMBEDDINGS:t=`
response = client.embeddings.create(
	input="${n||"Your string here"}",
	model="${k}",
	encoding_format="base64" # or "float"
)

print(response.data[0].embedding)
`;break;case i.TRANSCRIPTION:t=`
# Open the audio file
audio_file = open("path/to/your/audio/file.mp3", "rb")

# Make the transcription request
response = client.audio.transcriptions.create(
	model="${k}",
	file=audio_file${n?`,
	prompt="${n.replace(/\\/g,"\\\\").replace(/"/g,'\\"')}"`:""}
)

print(response.text)
`;break;case i.SPEECH:t=`
# Make the text-to-speech request
response = client.audio.speech.create(
	model="${k}",
	input="${n||"Your text to convert to speech here"}",
	voice="${c}"  # Options: alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer
)

# Save the audio to a file
output_filename = "output_speech.mp3"
response.stream_to_file(output_filename)
print(f"Audio saved to {output_filename}")

# Optional: Customize response format and speed
# response = client.audio.speech.create(
#     model="${k}",
#     input="${n||"Your text to convert to speech here"}",
#     voice="alloy",
#     response_format="mp3",  # Options: mp3, opus, aac, flac, wav, pcm
#     speed=1.0  # Range: 0.25 to 4.0
# )
# response.stream_to_file("output_speech.mp3")
`;break;default:t="\n# Code generation for this endpoint is not implemented yet."}return`${N}
${t}`}],909947)},899426,e=>{"use strict";let t=e=>e.trim().toLowerCase();function r(e,r){let a=t(e);if(""===a)return!0;let i=r.filter(e=>"string"==typeof e).map(e=>e.toLowerCase());return!!i.some(e=>e.includes(a))||a.split(/\s+/).every(e=>i.some(t=>t.includes(e)))}e.s(["filterBySearchTerm",0,function(e,t,a){return e.filter(e=>r(t,a(e)))},"matchesSearchTerm",0,r,"rankBySearchRelevance",0,function(e,r,a){let i=t(r);if(""===i)return[...e];let s=e=>{let t=a(e).toLowerCase();return 1e3*(t===i)+100*!!t.startsWith(i)+(1e3-t.length)};return[...e].sort((e,t)=>s(t)-s(e))}])},652272,209261,e=>{"use strict";var t=e.i(843476),r=e.i(271645),a=e.i(871689),i=e.i(643531),s=e.i(174886),n=e.i(306228),o=e.i(196631);let l=/^[a-zA-Z0-9][a-zA-Z0-9._-]*(\/[a-zA-Z0-9][a-zA-Z0-9._-]*)*$/,d=e=>e.trim().replace(/\/+$/,""),p=/\.(md|markdown|txt|json|ya?ml|toml)$/i,m=/^\d{1,3}(\.\d{1,3}){3}$/,c=/^[A-Za-z0-9-]+$/,u=/^[A-Za-z0-9._-]+$/,g=e=>e.pathname.split("/").filter(e=>""!==e),f=e=>{let t=e.split("/").filter(e=>""!==e);return t[t.length-1]??""},h=e=>e.toLowerCase().replace(/[^a-z0-9-]+/g,"-").replace(/-+/g,"-").replace(/^-+|-+$/g,""),x=e=>JSON.stringify({extraKnownMarketplaces:{litellm:{source:{source:"url",url:`${e}/claude-code/marketplace.json`}}}},null,2),b=e=>`/plugin install ${e.name}@litellm`;e.s(["buildMarketplaceSettingsSnippet",0,x,"formatInstallCommand",0,b,"getCategoryBadgeColor",0,e=>{if(!e)return"gray";let t=e.toLowerCase();if(t.includes("development")||t.includes("dev"))return"blue";if(t.includes("productivity")||t.includes("workflow"))return"green";if(t.includes("learning")||t.includes("education"))return"purple";if(t.includes("security")||t.includes("safety"))return"red";if(t.includes("data")||t.includes("analytics"))return"orange";else if(t.includes("integration")||t.includes("api"))return"yellow";return"gray"},"isValidEmail",0,e=>!e||/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e),"isValidSemanticVersion",0,e=>!e||/^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$/.test(e),"isValidSubPath",0,e=>{let t=d(e);return""!==t&&l.test(t)},"parseKeywords",0,e=>e&&""!==e.trim()?e.split(",").map(e=>e.trim()).filter(e=>""!==e):[],"parseSkillSource",0,(e,t)=>{let r=(e=>{let t,r=e.trim();if(""===r||r.startsWith("//"))return null;let a=/^[a-z][a-z0-9+.-]*:\/\//i.test(r)?r:`https://${r}`;try{t=new URL(a)}catch{return null}return"https:"!==t.protocol||""!==t.username||""!==t.password||!t.hostname.includes(".")||t.hostname.startsWith("[")||m.test(t.hostname)?null:t})(e);if(!r)return null;if("github.com"===r.hostname.replace(/^www\./,""))return((e,t)=>{let r=g(e);if(r.length<2)return null;let a=r[0],i=r[1].replace(/\.git$/,"");if(!c.test(a)||!u.test(i))return null;let s=`${a}/${i}`,n=`https://github.com/${s}`,o={parsed:{source:"github",repo:s},label:`GitHub repo — ${s}`,suggestedName:h(i)};if(r.length>=4&&("tree"===r[2]||"blob"===r[2])){let e=r.slice(4),t=f(e.join("/")),a=p.test(t)?e.slice(0,-1):e;if(0===a.length)return o;let i=d(a.join("/"));return l.test(i)?{parsed:{source:"git-subdir",url:n,path:i},label:`GitHub subdir — ${s} @ ${i}`,suggestedName:h(f(i))}:null}if(2!==r.length)return null;let m=d(t??"");return""!==m?l.test(m)?{parsed:{source:"git-subdir",url:n,path:m},label:`GitHub subdir — ${s} @ ${m}`,suggestedName:h(f(m))}:null:o})(r,t);if(g(r).length<2)return null;let a=`${r.protocol}//${r.host}${r.pathname.replace(/\/+$/,"")}`,i=d(t??"");return""!==i?l.test(i)?{parsed:{source:"git-subdir",url:a,path:i},label:`Git subdir — ${a} @ ${i}`,suggestedName:h(f(i))}:null:{parsed:{source:"url",url:a},label:`Git repo — ${a}`,suggestedName:h(f(r.pathname).replace(/\.git$/,""))}},"validatePluginName",0,e=>!!e&&""!==e.trim()&&/^[a-z0-9-]+$/.test(e)],209261),e.s(["default",0,({skill:e,onBack:l})=>{let d,[p,m]=(0,r.useState)("overview"),[c,u]=(0,r.useState)(null),g=(e,t)=>{navigator.clipboard.writeText(e),u(t),setTimeout(()=>u(null),2e3)},f="github"===(d=e.source).source&&d.repo?`https://github.com/${d.repo}`:"git-subdir"===d.source&&d.url?d.path?`${d.url}/tree/main/${d.path}`:d.url:"url"===d.source&&d.url?d.url:null,h=b(e),_=x(window.location.origin),v=[...e.category?[{property:"Category",value:e.category}]:[],...e.domain?[{property:"Domain",value:e.domain}]:[],...e.namespace?[{property:"Namespace",value:e.namespace}]:[],...e.version?[{property:"Version",value:e.version}]:[],...e.author?.name?[{property:"Author",value:e.author.name}]:[],...e.created_at?[{property:"Added",value:new Date(e.created_at).toLocaleDateString()}]:[]];return(0,t.jsxs)("div",{className:"py-6 pl-0 pr-8",children:[(0,t.jsxs)("div",{onClick:l,className:"mb-6 inline-flex cursor-pointer items-center gap-1.5 text-sm text-muted-foreground",children:[(0,t.jsx)(a.ArrowLeft,{className:"size-3"}),(0,t.jsx)("span",{children:"Skills"})]}),(0,t.jsxs)("div",{className:"mb-2",children:[(0,t.jsx)("h1",{className:"m-0 text-[28px] font-normal leading-tight text-foreground",children:e.name}),e.description&&(0,t.jsx)("p",{className:"mb-0 ml-0 mr-0 mt-2 text-sm leading-relaxed text-muted-foreground",children:e.description})]}),(0,t.jsx)("div",{className:"mb-7 mt-6 border-b border-border",children:(0,t.jsx)("div",{className:"flex",children:[{key:"overview",label:"Overview"},{key:"usage",label:"How to Use"}].map(e=>(0,t.jsx)("div",{onClick:()=>m(e.key),className:(0,o.cn)("-mb-px cursor-pointer border-b-[3px] px-5 py-3 text-sm",p===e.key?"border-info font-medium text-info":"border-transparent font-normal text-muted-foreground"),children:e.label},e.key))})}),"overview"===p&&(0,t.jsxs)("div",{className:"flex gap-16",children:[(0,t.jsxs)("div",{className:"min-w-0 flex-1",children:[(0,t.jsx)("h2",{className:"m-0 mb-1 text-lg font-normal text-foreground",children:"Skill Details"}),(0,t.jsx)("p",{className:"m-0 mb-4 text-[13px] text-muted-foreground",children:"Metadata registered with this skill"}),(0,t.jsxs)("table",{className:"w-full border-collapse text-sm",children:[(0,t.jsx)("thead",{children:(0,t.jsxs)("tr",{className:"border-b border-border",children:[(0,t.jsx)("th",{className:"w-40 py-3 text-left font-medium text-muted-foreground",children:"Property"}),(0,t.jsx)("th",{className:"py-3 text-left font-medium text-muted-foreground",children:e.name})]})}),(0,t.jsx)("tbody",{children:v.map((e,r)=>(0,t.jsxs)("tr",{className:"border-b border-border",children:[(0,t.jsx)("td",{className:"py-3 text-foreground",children:e.property}),(0,t.jsx)("td",{className:"py-3 text-foreground",children:e.value})]},r))})]})]}),(0,t.jsxs)("div",{className:"w-60 shrink-0",children:[(0,t.jsxs)("div",{className:"mb-6",children:[(0,t.jsx)("div",{className:"mb-1 text-xs text-muted-foreground",children:"Status"}),(0,t.jsx)("span",{className:(0,o.cn)("rounded-xl px-2.5 py-[3px] text-xs font-medium",e.enabled?"bg-success/10 text-success":"bg-muted text-muted-foreground"),children:e.enabled?"Public":"Draft"})]}),f&&(0,t.jsxs)("div",{className:"mb-6",children:[(0,t.jsx)("div",{className:"mb-1 text-xs text-muted-foreground",children:"Source"}),(0,t.jsxs)("a",{href:f,target:"_blank",rel:"noopener noreferrer",className:"flex items-center gap-1 break-all text-[13px] text-info",children:[f.replace("https://",""),(0,t.jsx)(n.Link2,{className:"size-3 shrink-0"})]})]}),e.keywords&&e.keywords.length>0&&(0,t.jsxs)("div",{className:"mb-6",children:[(0,t.jsx)("div",{className:"mb-2 text-xs text-muted-foreground",children:"Tags"}),(0,t.jsx)("div",{className:"flex flex-wrap gap-1.5",children:e.keywords.map(e=>(0,t.jsx)("span",{className:"rounded-2xl border border-border bg-card px-3 py-1 text-xs text-foreground",children:e},e))})]}),(0,t.jsxs)("div",{children:[(0,t.jsx)("div",{className:"mb-1 text-xs text-muted-foreground",children:"Skill ID"}),(0,t.jsx)("div",{className:"break-all font-mono text-xs text-foreground",children:e.id})]})]})]}),"usage"===p&&(0,t.jsxs)("div",{className:"max-w-[640px]",children:[(0,t.jsx)("h2",{className:"m-0 mb-2 text-lg font-normal text-foreground",children:"Using this skill"}),(0,t.jsx)("p",{className:"m-0 mb-6 text-sm leading-relaxed text-muted-foreground",children:"Once your proxy is set as a marketplace, enable this skill in Claude Code with one command:"}),(0,t.jsxs)("div",{className:"mb-6 overflow-hidden rounded-lg border border-border",children:[(0,t.jsxs)("div",{className:"flex items-center justify-between border-b border-border bg-muted px-4 py-2.5",children:[(0,t.jsx)("span",{className:"text-[13px] font-medium text-foreground",children:"Run in Claude Code"}),(0,t.jsxs)("button",{onClick:()=>g(h,"install"),className:(0,o.cn)("flex cursor-pointer items-center gap-1 border-none bg-transparent p-0 text-xs","install"===c?"text-success":"text-info"),children:["install"===c?(0,t.jsx)(i.Check,{className:"size-3"}):(0,t.jsx)(s.Copy,{className:"size-3"}),"install"===c?"Copied":"Copy"]})]}),(0,t.jsx)("pre",{className:"m-0 bg-card px-4 py-3.5 font-mono text-sm text-foreground",children:h})]}),(0,t.jsxs)("div",{className:"mb-4 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3",children:[(0,t.jsxs)("p",{className:"m-0 mb-2 text-[13px] leading-relaxed text-muted-foreground",children:['If you see "Plugin ',e.name,'not found in marketplace", update the catalog first:']}),(0,t.jsx)("pre",{className:"m-0 bg-transparent font-mono text-[13px] text-foreground",children:"/plugin marketplace update litellm"})]}),(0,t.jsxs)("p",{className:"m-0 text-[13px] leading-relaxed text-muted-foreground",children:["Don't have the marketplace configured yet?"," ",(0,t.jsx)("span",{onClick:()=>m("setup"),className:"cursor-pointer text-info",children:"See one-time setup →"})]})]}),"setup"===p&&(0,t.jsxs)("div",{className:"max-w-[640px]",children:[(0,t.jsx)("h2",{className:"m-0 mb-2 text-lg font-normal text-foreground",children:"One-time marketplace setup"}),(0,t.jsx)("p",{className:"m-0 mb-3 text-sm leading-relaxed text-muted-foreground",children:"Run this command in Claude Code to register the marketplace:"}),(0,t.jsxs)("div",{className:"mb-6 overflow-hidden rounded-lg border border-border",children:[(0,t.jsxs)("div",{className:"flex items-center justify-between border-b border-border bg-muted px-4 py-2.5",children:[(0,t.jsx)("span",{className:"text-[13px] font-medium text-foreground",children:"Run in Claude Code"}),(0,t.jsxs)("button",{onClick:()=>{let e=window.location.origin;g(`/plugin marketplace add ${e}/claude-code/marketplace.json`,"marketplace-cmd")},className:(0,o.cn)("flex cursor-pointer items-center gap-1 border-none bg-transparent p-0 text-xs","marketplace-cmd"===c?"text-success":"text-info"),children:["marketplace-cmd"===c?(0,t.jsx)(i.Check,{className:"size-3"}):(0,t.jsx)(s.Copy,{className:"size-3"}),"marketplace-cmd"===c?"Copied":"Copy"]})]}),(0,t.jsx)("pre",{className:"m-0 bg-card px-4 py-3.5 font-mono text-[13px] text-foreground",children:`/plugin marketplace add ${window.location.origin}/claude-code/marketplace.json`})]}),(0,t.jsxs)("p",{className:"m-0 mb-3 text-sm leading-relaxed text-muted-foreground",children:["Or add this to ",(0,t.jsx)("code",{className:"rounded bg-muted px-1.5 py-px text-[13px]",children:"~/.claude/settings.json"})," ","for a persistent configuration:"]}),(0,t.jsxs)("div",{className:"overflow-hidden rounded-lg border border-border",children:[(0,t.jsxs)("div",{className:"flex items-center justify-between border-b border-border bg-muted px-4 py-2.5",children:[(0,t.jsx)("span",{className:"text-[13px] font-medium text-foreground",children:"~/.claude/settings.json"}),(0,t.jsxs)("button",{onClick:()=>g(_,"settings"),className:(0,o.cn)("flex cursor-pointer items-center gap-1 border-none bg-transparent p-0 text-xs","settings"===c?"text-success":"text-info"),children:["settings"===c?(0,t.jsx)(i.Check,{className:"size-3"}):(0,t.jsx)(s.Copy,{className:"size-3"}),"settings"===c?"Copied":"Copy"]})]}),(0,t.jsx)("pre",{className:"m-0 bg-card px-4 py-3.5 font-mono text-[13px] text-foreground",children:_})]})]})]})}],652272)},157058,e=>{"use strict";var t=e.i(843476),r=e.i(934879),a=e.i(976883),i=e.i(135214),s=e.i(708347);e.s(["default",0,function(){let{accessToken:e,userRole:n,premiumUser:o}=(0,i.default)();return(0,s.isAdminRole)(n)?(0,t.jsx)(r.default,{accessToken:e,publicPage:!1,premiumUser:o,userRole:n}):(0,t.jsx)(a.default,{accessToken:e,isEmbedded:!0})}])}]);